"""RAG pipeline: retrieve relevant chunks, generate answer with LLM."""

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.llm_client import LLMClient
from academic_intelligence_ai.query.search import Searcher

logger = get_logger("query.rag")

SYSTEM_PROMPT = """Ti si asistent za studente Prirodno-matematičkog fakulteta Univerziteta u Novom Sadu.
Odgovaraj na srpskom jeziku, koncizno i tačno, koristeći isključivo informacije iz priloženog konteksta.
Ako odgovor nije u kontekstu, reci: "Sistem ne poseduje tu informaciju."
Ne izmišljaj informacije."""


class RAGPipeline:
    """Single-pass RAG: retrieve top-k chunks, generate answer."""

    def __init__(self, top_k: int = 5):
        self.searcher = Searcher()
        self.llm = LLMClient()
        self.top_k = top_k

    def ask(self, query: str) -> dict:
        """Run RAG for a single query.

        Returns:
            answer: str
            chunks: list of retrieved chunk dicts
            latency_ms: total latency
            prompt_tokens: int
            response_tokens: int
        """
        chunks = self.searcher.search(query, top_k=self.top_k)

        context = "\n\n".join(
            f"[Izvor: {c['url']}]\n{c['text']}"
            for c in chunks
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Kontekst:\n{context}\n\nPitanje: {query}"},
        ]

        result = self.llm.generate(messages)

        return {
            "answer": result.get("answer", ""),
            "chunks": chunks,
            "latency_ms": result.get("latency_ms", 0),
            "prompt_tokens": result.get("prompt_tokens", 0),
            "response_tokens": result.get("response_tokens", 0),
        }
