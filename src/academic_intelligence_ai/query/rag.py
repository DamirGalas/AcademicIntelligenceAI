"""RAG pipeline: retrieve relevant chunks, generate answer with LLM.

Two modes:
  RAGPipeline     — classic pipeline: always search, inject context, generate
  RAGToolPipeline — tool calling: LLM decides when/how to search using OpenAI function calling
"""

import json

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.llm_client import LLMClient
from academic_intelligence_ai.query.search import Searcher

logger = get_logger("query.rag")

_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "Pretražuje bazu znanja Prirodno-matematičkog fakulteta u Novom Sadu. "
            "Koristi za pronalaženje informacija o studijskim programima, profesorima, "
            "kontaktima, departmanima i svim akademskim temama."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Upit za pretragu baze znanja.",
                }
            },
            "required": ["query"],
        },
    },
}

SYSTEM_PROMPT = """Ti si asistent za studente Prirodno-matematičkog fakulteta Univerziteta u Novom Sadu.
Odgovaraj na srpskom jeziku, koncizno i tačno, koristeći isključivo informacije iz priloženog konteksta.
Ako odgovor nije u kontekstu, reci: "Sistem ne poseduje tu informaciju." — bez navođenja izvora.
Ne izmišljaj informacije.
Na kraju odgovora navedi jedan najrelevantniji izvor u formatu [Izvor: URL]. Izostaviti izvor samo ako sistem ne poseduje informaciju.

Primeri željenih odgovora:

Pitanje: Koji je email profesora Borisa Šobota na DMI?
Odgovor: Email profesora Borisa Šobota je sobot@dmi.uns.ac.rs. [Izvor: https://www.dmi.uns.ac.rs/imenik/boris-sobot/]

Pitanje: Da li DMI ima doktorske studije iz informatike?
Odgovor: Da, DMI ima doktorske akademske studije informatike (3 godine, 180 ESPB). [Izvor: https://www.dmi.uns.ac.rs/studijski-programi/]

Pitanje: Kolika je cena smeštaja u studentskom domu za studente?
Odgovor: Sistem ne poseduje tu informaciju.

Pitanje: Kako se prijaviti na probni prijemni ispit na PMF-u?
Odgovor: Probni ispit organizuju Studentski parlament i Savez studenata PMF-a. Prijava je besplatna putem onlajn formulara koji se objavljuje na sajtu departmana. [Izvor: https://www.pmf.uns.ac.rs/]"""


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


class RAGToolPipeline:
    """Tool-calling RAG: LLM decides when and how to search using OpenAI function calling.

    Flow:
      1. LLM receives the user question + search tool definition (no context yet)
      2. LLM calls search_knowledge_base(query) — may reformulate the query
      3. Execute search, pass results back to LLM as tool result
      4. LLM generates final answer grounded in retrieved chunks
    """

    def __init__(self, top_k: int = 5):
        self.searcher = Searcher()
        self.llm = LLMClient()
        self.top_k = top_k

    def ask(self, query: str) -> dict:
        """Run tool-calling RAG for a single query.

        Returns same structure as RAGPipeline.ask().
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        total_prompt_tokens = 0
        total_response_tokens = 0
        total_latency_ms = 0
        chunks: list[dict] = []

        # Step 1: LLM decides whether and how to search
        result = self.llm.generate(messages, tools=[_SEARCH_TOOL])
        total_prompt_tokens += result.get("prompt_tokens", 0)
        total_response_tokens += result.get("response_tokens", 0)
        total_latency_ms += result.get("latency_ms", 0)

        if result["type"] == "tool_call":
            search_query = result["tool_arguments"].get("query", query)
            logger.info("Tool call: search_knowledge_base('%s')", search_query[:80])

            # Step 2: Execute search
            chunks = self.searcher.search(search_query, top_k=self.top_k)
            context = "\n\n".join(f"[Izvor: {c['url']}]\n{c['text']}" for c in chunks)

            # Step 3: Pass tool result back and generate final answer
            messages = messages + [
                {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": result["tool_call_id"],
                        "type": "function",
                        "function": {
                            "name": "search_knowledge_base",
                            "arguments": json.dumps(result["tool_arguments"]),
                        },
                    }],
                },
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": context,
                },
            ]

            final = self.llm.generate(messages)
            total_prompt_tokens += final.get("prompt_tokens", 0)
            total_response_tokens += final.get("response_tokens", 0)
            total_latency_ms += final.get("latency_ms", 0)
            answer = final.get("answer", "")
        else:
            # LLM answered directly without searching
            answer = result.get("answer", "")

        return {
            "answer": answer,
            "chunks": chunks,
            "latency_ms": total_latency_ms,
            "prompt_tokens": total_prompt_tokens,
            "response_tokens": total_response_tokens,
        }
