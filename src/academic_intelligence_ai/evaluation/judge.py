"""LLM-as-judge for E2E RAG evaluation.

Evaluates generated answers on two dimensions:
  - correctness:   does the answer match the expected answer in substance?
  - faithfulness:  are the claims grounded in the retrieved chunks?

Scoring: 1=fail, 2=partial, 3=pass
"""

import json

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.llm_client import LLMClient

logger = get_logger("evaluation.judge")

_CORRECTNESS_PROMPT = """Ti si evaluator kvaliteta AI odgovora. Oceni da li je generisani odgovor tačan.
Generisani odgovor je dobijen od RAG sistema tako da može da bude tačan, može da bude delimično tačan a može se desiti da nema nikakve veze sa pitanjem.
Tvoja uloga je da pomogneš da otkrijemo na kojim mestima ne radi dobro kako bismo ga poboljšali.

Pitanje: **{query}**
Tip pitanja: **{answer_type}**
Očekivani odgovor: **{expected}**
Generisani odgovor: **{generated}**

Oceni TAČNOST na skali 1-3:
3 = Tačan i potpun (sadrži sve ključne informacije iz očekivanog odgovora)
2 = Delimično tačan (sadrži neke tačne informacije ali nedostaje nešto važno ili ima manju grešku)
1 = Netačan (pogrešne informacije, halucinacija, ili potpuno promašen odgovor)

Posebna pravila po tipu pitanja:
- "unanswerable": ocena 3 ako sistem kaže da ne zna, ocena 1 ako izmisli odgovor
- "boolean": ocena 3 ako je da/ne odgovor tačan — detalji nisu obavezni za pun bod. Mora da bude neosporno da je odgovor tačan. Ukoliko postoji sumnja onda to treba da bude navedeno u odgovoru.
- "factual": strogo proveravaj tačnost konkretnih podataka (emailovi, telefoni, imena)
- "procedural": ocena 3 ako su navedeni ispravni koraci, čak i bez svih detalja. Detalji moraju da budu u generisanim odgovorima. Ne mogu da se izmisljaju.

Odgovori ISKLJUČIVO u JSON formatu:
{{"correctness": <1|2|3>, "reasoning": "<kratko objašnjenje>"}}

Proveri da li je procena uradjena u kontekstu tipa pitanja.
"""

_FAITHFULNESS_PROMPT = """Ti si evaluator kvaliteta AI odgovora. Oceni da li je odgovor zasnovan na priloženom kontekstu.

Pitanje: **{query}**
Tip pitanja: **{answer_type}**
Generisani odgovor: **{generated}**

Kontekst koji je sistem koristio:
{context}

Oceni POUZDANOST na skali 1-3:
3 = Sve tvrdnje su podržane kontekstom
2 = Većina tvrdnji je iz konteksta, ali postoji neka informacija koja nije direktno potvrđena
1 = Odgovor sadrži informacije kojih nema u kontekstu (halucinacija)

Posebno pravilo:
- "unanswerable": ako sistem kaže da ne poseduje informaciju — ocena 3, bez obzira na kontekst

Odgovori ISKLJUČIVO u JSON formatu:
{{"faithfulness": <1|2|3>, "reasoning": "<kratko objašnjenje>"}}"""


class Judge:
    """Evaluates RAG answers using a separate LLM call."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        # Judge uses a separate LLMClient instance with higher-quality model
        self.llm = LLMClient()
        self.llm.model = model
        self.llm.temperature = 0.0

    def evaluate(
        self,
        query: str,
        expected_answer: str,
        generated_answer: str,
        answer_type: str,
        chunks: list[dict],
    ) -> dict:
        """Evaluate a single answer.

        Returns:
            correctness: 1-3
            faithfulness: 1-3
            correctness_reasoning: str
            faithfulness_reasoning: str
            tokens: int (total tokens used)
        """
        correctness, c_reasoning, c_tokens = self._judge_correctness(
            query, expected_answer, generated_answer, answer_type
        )
        faithfulness, f_reasoning, f_tokens = self._judge_faithfulness(
            query, generated_answer, answer_type, chunks
        )

        return {
            "correctness": correctness,
            "faithfulness": faithfulness,
            "correctness_reasoning": c_reasoning,
            "faithfulness_reasoning": f_reasoning,
            "judge_tokens": c_tokens + f_tokens,
        }

    def _judge_correctness(
        self,
        query: str,
        expected: str,
        generated: str,
        answer_type: str,
    ) -> tuple[int, str, int]:
        prompt = _CORRECTNESS_PROMPT.format(
            query=query,
            answer_type=answer_type,
            expected=expected,
            generated=generated,
        )
        result = self.llm.generate([{"role": "user", "content": prompt}])
        return self._parse_result(result, "correctness")

    def _judge_faithfulness(
        self,
        query: str,
        generated: str,
        answer_type: str,
        chunks: list[dict],
    ) -> tuple[int, str, int]:
        context = "\n\n".join(f"[{c['url']}]\n{c['text']}" for c in chunks)
        prompt = _FAITHFULNESS_PROMPT.format(
            query=query,
            answer_type=answer_type,
            generated=generated,
            context=context,
        )
        result = self.llm.generate([{"role": "user", "content": prompt}])
        return self._parse_result(result, "faithfulness")

    def _parse_result(self, result: dict, key: str) -> tuple[int, str, int]:
        tokens = result.get("prompt_tokens", 0) + result.get("response_tokens", 0)
        try:
            text = result.get("answer", "{}")
            # Strip markdown code fences if present
            text = (
                text.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            data = json.loads(text)
            score = max(1, min(3, int(data.get(key, 1))))
            reasoning = data.get("reasoning", "")
            return score, reasoning, tokens
        except Exception as e:
            logger.warning(
                "Failed to parse judge response for %s: %s | raw: %s",
                key,
                e,
                result.get("answer", ""),
            )
            return 1, "parse error", tokens
