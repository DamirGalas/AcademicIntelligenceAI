import json
import time
from pathlib import Path

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.llm_client import LLMClient
from academic_intelligence_ai.query.search import Searcher

logger = get_logger("query.agent")

PROJECT_ROOT = Path(__file__).resolve().parents[3]

SYSTEM_PROMPT = (
    "Ti si pomoćnik za studente Prirodno-matematičkog fakulteta u Novom Sadu. "
    "Odgovaraj isključivo na osnovu informacija koje dobiješ pretraživanjem baze znanja. "
    "Ako pretraga ne vrati relevantne informacije, reci da nemaš tu informaciju. "
    "Odgovaraj na srpskom jeziku, kratko i precizno."
)

REWRITE_SYSTEM_PROMPT = """Ti ispravljaš pravopisne greške i dijakritiku u pitanjima korisnika.

Pravila:
- Vrati SAMO ispravljenu rečenicu, bez objašnjenja
- Zadrži originalno značenje i formu pitanja
- Ispravi greške u pisanju i dodaj dijakritiku gdje nedostaje (č, ć, š, ž, đ)
- Ako nema grešaka, vrati pitanje nepromenjeno

Primeri:
Pitanje: Ko su profesori u penziji na Departmanu za matematiku i informatiku?
Ko su profesori u penziji na Departmanu za matematiku i informatiku?

Pitanje: U kojoj sali se polaze prijemni ispit za informaticke smerove?
U kojoj sali se polaže prijemni ispit za informatičke smerove?

Pitanje: Koji je mejl profesora Kovacevic sa DBE?
Koji je email profesora Kovačević sa DBE?"""

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_knowledge_base",
        "description": (
            "Pretražuje bazu znanja PMF Novi Sad i vraća relevantne odlomke teksta. "
            "Koristi ovaj alat kada ti je potrebna konkretna informacija o fakultetu, "
            "studijskim programima, osoblju, obavještenjima ili aktivnostima."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Upit za semantičku pretragu baze znanja. "
                        "Piši kao ključne riječi ili kratku frazu — ne kao pitanje. "
                        "Koristi srpski jezik. "
                        "Budi konkretan: uključi ime departmana, predmeta ili osobe ako je relevantno. "
                        "Primjeri: 'dekan PMF Novi Sad', 'prijemni ispit matematika DMI sala', "
                        "'studijski programi Departman za fiziku'."
                    ),
                }
            },
            "required": ["query"],
        },
    },
}


def _format_chunks_for_tool_result(chunks: list[dict]) -> str:
    """Format retrieved chunks as a tool result string for the LLM."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(f"[{i}] (izvor: {chunk['source']})\n{chunk['text']}")
    return "\n\n".join(parts)


class Agent:
    """LLM agent with tool calling. Decides whether and how to search, then answers."""

    def __init__(self):
        self.searcher = Searcher()
        self.llm = LLMClient()
        logger.info("Agent ready")

    def rewrite_query(self, user_query: str) -> str:
        """Correct spelling and diacritics in a user query.

        Used by retrieval eval to measure whether spelling correction improves retrieval.
        Returns the corrected query string, or the original on failure.
        """
        messages = [
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Pitanje: {user_query}"},
        ]
        result = self.llm.generate(messages)
        rewritten = result.get("answer", "").strip()
        if not rewritten:
            logger.warning("Query rewrite failed, using original: '%s'", user_query[:80])
            return user_query
        logger.info("Query rewrite: '%s' -> '%s'", user_query[:60], rewritten[:60])
        return rewritten

    def ask(self, user_query: str) -> dict:
        """Answer a query. LLM decides whether to search and formulates its own search query.

        Returns a dict with keys: answer, sources, num_chunks, top_score, fallback,
        used_tool, tool_query.
        """
        start = time.perf_counter()
        total_prompt_tokens = 0
        total_response_tokens = 0
        total_llm_latency_ms = 0

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query},
        ]

        # First LLM call — with tool available
        first_result = self.llm.generate(messages, tools=[SEARCH_TOOL])
        total_prompt_tokens += first_result["prompt_tokens"]
        total_response_tokens += first_result["response_tokens"]
        total_llm_latency_ms += first_result["latency_ms"]

        chunks = []
        tool_query = None
        used_tool = False

        if first_result["type"] == "tool_call":
            used_tool = True
            tool_query = first_result["tool_arguments"]["query"]
            chunks = self.searcher.search(tool_query)

            logger.info("Tool call: query='%s' -> %d chunks", tool_query[:80], len(chunks))

            # Append LLM's tool call decision to messages
            messages.append({
                "role": "assistant",
                "tool_calls": [{
                    "id": first_result["tool_call_id"],
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "arguments": json.dumps(first_result["tool_arguments"]),
                    },
                }],
            })

            # Append tool result
            tool_content = (
                _format_chunks_for_tool_result(chunks)
                if chunks
                else "Nisu pronađeni relevantni rezultati za ovaj upit."
            )
            messages.append({
                "role": "tool",
                "tool_call_id": first_result["tool_call_id"],
                "content": tool_content,
            })

            # Second LLM call — generate final answer from search results
            second_result = self.llm.generate(messages)
            total_prompt_tokens += second_result["prompt_tokens"]
            total_response_tokens += second_result["response_tokens"]
            total_llm_latency_ms += second_result["latency_ms"]
            answer = second_result["answer"]

        else:
            # LLM answered directly without searching
            answer = first_result["answer"]

        total_ms = round((time.perf_counter() - start) * 1000)
        top_score = chunks[0]["score"] if chunks else 0.0
        fallback = used_tool and not chunks

        logger.info(
            "Agent answer for '%s': used_tool=%s, chunks=%d, top=%.3f, llm=%dms, total=%dms",
            user_query[:50], used_tool, len(chunks), top_score,
            total_llm_latency_ms, total_ms,
        )

        return {
            "answer": answer,
            "sources": list({c["source"] for c in chunks}),
            "num_chunks": len(chunks),
            "top_score": top_score,
            "fallback": fallback,
            "used_tool": used_tool,
            "tool_query": tool_query,
        }


def run():
    """Interactive agent loop for testing."""
    agent = Agent()
    print("\nAgent ready. Type a question (or 'q' to quit).\n")

    while True:
        query = input("Pitanje: ").strip()
        if not query or query.lower() == "q":
            break

        result = agent.ask(query)

        print(f"\nOdgovor: {result['answer']}")
        if result["used_tool"]:
            print(f"  Tool query: {result['tool_query']}")
        print(f"  Izvori: {', '.join(result['sources']) or 'nema'}")
        print(f"  Chunks: {result['num_chunks']}, Top score: {result['top_score']:.3f}")
        print(f"  Fallback: {'da' if result['fallback'] else 'ne'}\n")


if __name__ == "__main__":
    run()
