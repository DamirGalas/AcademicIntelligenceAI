"""FastAPI web app — search interface for the PMF Academic Intelligence system."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from academic_intelligence_ai.query.rag import RAGToolPipeline

app = FastAPI(title="PMF Academic Intelligence")

_BASE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_BASE / "static"), name="static")
templates = Jinja2Templates(directory=_BASE / "templates")

_rag = RAGToolPipeline()

SOURCES = [
    ("PMF", "https://www.pmf.uns.ac.rs"),
    ("DMI", "https://www.dmi.uns.ac.rs"),
    ("Fizika", "https://www.df.uns.ac.rs"),
    ("Hemija", "https://www.dh.uns.ac.rs"),
    ("Biologija", "https://wwwold.dbe.pmf.uns.ac.rs"),
    ("Geografija", "https://www.dgt.uns.ac.rs"),
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

    chunk_sources = list(dict.fromkeys(
        c["url"] for c in result.get("chunks", []) if c.get("url")
    ))

    return {"answer": answer, "sources": chunk_sources}
