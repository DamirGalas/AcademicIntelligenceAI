import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.llm_client import LLMClient
from academic_intelligence_ai.query.search import Searcher

logger = get_logger("query.rag")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "academic.db"

SYSTEM_PROMPT = (
    "Ti si pomoćnik za studente Prirodno-matematičkog fakulteta u Novom Sadu. "
    "Odgovaraj isključivo na osnovu datog konteksta. "
    "Ako kontekst ne sadrži odgovor, reci da nemaš tu informaciju. "
    "Odgovaraj na srpskom jeziku, kratko i precizno."
)


def _init_query_metrics_table():
    """Create the query_metrics table if it does not exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            query TEXT NOT NULL,
            num_chunks INTEGER NOT NULL,
            top_score REAL NOT NULL,
            avg_top3_score REAL NOT NULL,
            fallback INTEGER NOT NULL,
            prompt_tokens INTEGER NOT NULL,
            response_tokens INTEGER NOT NULL,
            llm_latency_ms INTEGER NOT NULL,
            total_latency_ms INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def build_prompt(query: str, chunks: list[dict]) -> str:
    """Build a RAG prompt from the query and retrieved chunks."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"[{i}] (izvor: {chunk['source']}) {chunk['text']}")

    context = "\n\n".join(context_parts)

    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- KONTEKST ---\n{context}\n\n"
        f"--- PITANJE ---\n{query}\n\n"
        f"--- ODGOVOR ---\n"
    )


class RAG:
    """Retrieval-Augmented Generation: search + LLM answer."""

    def __init__(self):
        self.searcher = Searcher()
        self.llm = LLMClient()
        _init_query_metrics_table()
        logger.info("RAG system ready")

    def _log_metrics(self, query: str, num_chunks: int, top_score: float,
                     avg_top3: float, fallback: bool, llm_metrics: dict,
                     total_ms: int):
        """Write query metrics to SQLite."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                """INSERT INTO query_metrics
                   (timestamp, query, num_chunks, top_score, avg_top3_score,
                    fallback, prompt_tokens, response_tokens, llm_latency_ms, total_latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    query,
                    num_chunks,
                    round(top_score, 4),
                    round(avg_top3, 4),
                    int(fallback),
                    llm_metrics.get("prompt_tokens", 0),
                    llm_metrics.get("response_tokens", 0),
                    llm_metrics.get("latency_ms", 0),
                    total_ms,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("Failed to log query metrics: %s", e)

    def ask(self, query: str) -> dict:
        """Answer a query using retrieval + LLM.

        Returns a dict with keys: answer, sources, num_chunks, top_score, fallback.
        """
        start = time.perf_counter()

        chunks = self.searcher.search(query)

        if not chunks:
            logger.warning("Fallback triggered for query: '%s'", query[:80])
            total_ms = round((time.perf_counter() - start) * 1000)
            self._log_metrics(query, 0, 0.0, 0.0, True, {}, total_ms)
            return {
                "answer": "Nisam pronašao relevantne informacije za ovo pitanje.",
                "sources": [],
                "num_chunks": 0,
                "top_score": 0.0,
                "fallback": True,
            }

        prompt = build_prompt(query, chunks)
        llm_result = self.llm.generate(prompt)

        total_ms = round((time.perf_counter() - start) * 1000)
        sources = list({c["source"] for c in chunks})
        top_score = chunks[0]["score"]
        top3_scores = [c["score"] for c in chunks[:3]]
        avg_top3 = sum(top3_scores) / len(top3_scores)

        self._log_metrics(query, len(chunks), top_score, avg_top3, False, llm_result, total_ms)

        logger.info(
            "RAG answer for '%s': %d chunks, top=%.3f, llm=%dms, total=%dms",
            query[:50], len(chunks), top_score, llm_result["latency_ms"], total_ms,
        )

        return {
            "answer": llm_result["answer"],
            "sources": sources,
            "num_chunks": len(chunks),
            "top_score": top_score,
            "fallback": False,
        }


def run():
    """Interactive RAG loop for testing."""
    rag = RAG()
    print("\nRAG system ready. Type a question (or 'q' to quit).\n")

    while True:
        query = input("Pitanje: ").strip()
        if not query or query.lower() == "q":
            break

        result = rag.ask(query)

        print(f"\nOdgovor: {result['answer']}")
        print(f"  Izvori: {', '.join(result['sources'])}")
        print(f"  Chunks: {result['num_chunks']}, Top score: {result['top_score']:.3f}")
        print(f"  Fallback: {'da' if result['fallback'] else 'ne'}\n")


if __name__ == "__main__":
    run()
