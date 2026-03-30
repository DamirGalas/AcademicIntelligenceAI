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
                    "description": (
                        "Upit za pretragu baze znanja. "
                        "Formuliši kao konkretno pitanje, a ne kao niz ključnih reči. "
                        "Budi što specifičniji — što precizniji upit, bolji rezultati pretrage."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Kratko objašnjenje zašto pozivаš pretragu. "
                        "Ako si podelio pitanje na više upita, navedi sva podpitanja i objasni koja ovaj upit pokriva."
                    ),
                },
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

Obrati pažnju da su određena pitanja složena, odnosno da se sastoje od više pitanja. To mogu da budu pitanja koja traže poređenja između dve stvari ili da iz nekog drugog razloga ima više delova pitanja. 
Kada se pojave takva pitanja onda ih razdvoj na odvojena pitanja i potraži izvore za svako od njih zasebno. Pa tek kada imaš sve potrebne izvore napiši odgovor.

Primeri željenih odgovora:

Pitanje: Koji je email profesora Borisa Šobota na DMI?
Odgovor: Email profesora Borisa Šobota je sobot@dmi.uns.ac.rs. [Izvor: https://www.dmi.uns.ac.rs/imenik/boris-sobot/]

Pitanje: Da li DMI ima doktorske studije iz informatike?
Odgovor: Da, DMI ima doktorske akademske studije informatike (3 godine, 180 ESPB). [Izvor: https://www.dmi.uns.ac.rs/studijski-programi/]

Pitanje: Kolika je cena smeštaja u studentskom domu za studente?
Odgovor: Sistem ne poseduje tu informaciju.

Pitanje: Kako se prijaviti na probni prijemni ispit na PMF-u?
Odgovor: Probni ispit organizuju Studentski parlament i Savez studenata PMF-a. Prijava je besplatna putem onlajn formulara koji se objavljuje na sajtu departmana. [Izvor: https://www.pmf.uns.ac.rs/]

Pitanje: Ko su prodekani za nastavu i nauku na PMF-u?
Odgovor: Prodekan za nastavu je dr Ljubica Ivanović Bibić (tel. +381-21-485-2717, nastava@pmf.uns.ac.rs). Prodekan za nauku je dr Dušan Mrđa (tel. +381-21-485-2703, nauka@pmf.uns.ac.rs). [Izvor: https://www.pmf.uns.ac.rs/]

Pitanje: Koje master studije nudi Departman za fiziku, a koje Departman za matematiku i informatiku?
Odgovor: Departman za fiziku nudi master akademske studije Fizika i Nastava fizike, kao i master strukovne studije Optometrija. DMI nudi master programe: Matematika, Primenjena matematika, Master profesor matematike, Data Science, Računarske nauke, Informacione tehnologije i Veštačka inteligencija. [Izvor: https://www.df.uns.ac.rs/studijski-programi/, https://www.dmi.uns.ac.rs/studijski-programi/]"""


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

        context = "\n\n".join(f"[Izvor: {c['url']}]\n{c['text']}" for c in chunks)

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

    def ask(self, query: str, max_tool_calls: int = 3) -> dict:
        """Run tool-calling RAG for a single query.

        LLM may call search_knowledge_base multiple times (e.g. for multi-part
        or comparative questions). Loop continues until the LLM returns a final
        answer or max_tool_calls is reached.

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
        answer = ""

        first_call = True
        for _ in range(max_tool_calls + 1):
            tool_choice = "required" if first_call else "auto"
            first_call = False
            result = self.llm.generate(messages, tools=[_SEARCH_TOOL], tool_choice=tool_choice)
            total_prompt_tokens += result.get("prompt_tokens", 0)
            total_response_tokens += result.get("response_tokens", 0)
            total_latency_ms += result.get("latency_ms", 0)

            if result["type"] != "tool_call":
                answer = result.get("answer", "")
                break

            search_query = result["tool_arguments"].get("query", query)
            reasoning = result["tool_arguments"].get("reasoning", "")
            tool_call_num = len([m for m in messages if m.get("role") == "tool"]) + 1
            logger.info("Tool call #%d: search_knowledge_base('%s')", tool_call_num, search_query[:80])
            if reasoning:
                logger.info("  Reasoning: %s", reasoning)

            new_chunks = self.searcher.search(search_query, top_k=self.top_k)
            chunks.extend(new_chunks)
            context = "\n\n".join(f"[Izvor: {c['url']}]\n{c['text']}" for c in new_chunks)
            messages = messages + [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": result["tool_call_id"],
                            "type": "function",
                            "function": {
                                "name": "search_knowledge_base",
                                "arguments": json.dumps(result["tool_arguments"]),
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": context,
                },
            ]

        if not answer:
            answer = "Sistem ne poseduje tu informaciju."

        return {
            "answer": answer,
            "chunks": chunks,
            "latency_ms": total_latency_ms,
            "prompt_tokens": total_prompt_tokens,
            "response_tokens": total_response_tokens,
        }
