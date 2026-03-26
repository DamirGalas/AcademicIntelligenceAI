"""FastAPI web app — search interface for the PMF Academic Intelligence system."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from academic_intelligence_ai.db.connection import get_connection
from academic_intelligence_ai.query.rag import RAGToolPipeline

app = FastAPI(title="PMF Academic Intelligence")

_BASE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
templates = Jinja2Templates(directory=_BASE / "templates")

_rag = RAGToolPipeline()

SOURCES = [
    ("PMF", "https://www.pmf.uns.ac.rs"),
    ("Matematika i informatika", "https://www.dmi.uns.ac.rs"),
    ("Fizika", "https://www.df.uns.ac.rs"),
    ("Hemija", "https://www.dh.uns.ac.rs"),
    ("Biologija i ekologija", "https://wwwold.dbe.pmf.uns.ac.rs"),
    ("Geografija, turizam i hotelijerstvo", "https://www.dgt.uns.ac.rs"),
]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"sources": SOURCES},
    )


@app.post("/ask")
async def ask(request: Request):
    body = await request.json()
    query = (body.get("query") or "").strip()
    if not query:
        return {"answer": "Unesite pitanje.", "sources": []}

    result = _rag.ask(query)
    answer = result.get("answer", "")
    chunks = result.get("chunks", [])

    chunk_sources = list(dict.fromkeys(
        c["url"] for c in chunks if c.get("url")
    ))

    conn = get_connection()
    conn.execute(
        """INSERT INTO query_log
           (query, answer, num_chunks, top_chunk_url, prompt_tokens, response_tokens, latency_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            query,
            answer,
            len(chunks),
            chunk_sources[0] if chunk_sources else "",
            result.get("prompt_tokens", 0),
            result.get("response_tokens", 0),
            result.get("latency_ms", 0),
        ),
    )
    conn.commit()

    return {"answer": answer, "sources": chunk_sources}
