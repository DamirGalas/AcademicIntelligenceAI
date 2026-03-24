"""End-to-end RAG evaluation.

For each question in test_answers.json:
  1. Run RAG pipeline (search + LLM answer)
  2. Judge the answer (correctness + faithfulness)
  3. Persist results to e2e_eval_runs table

Usage:
    python -m academic_intelligence_ai.evaluation.e2e_eval
    python -m academic_intelligence_ai.evaluation.e2e_eval --note "baseline before cp13"
    python -m academic_intelligence_ai.evaluation.e2e_eval --limit 5  # quick smoke test
"""

import json
import sys
from pathlib import Path

from academic_intelligence_ai.db.connection import get_connection
from academic_intelligence_ai.evaluation.judge import Judge
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.rag import RAGPipeline

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

logger = get_logger("evaluation.e2e_eval")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run(note: str = "", limit: int = 0, top_k: int = 5, judge_model: str = "gpt-4o"):
    """Run E2E evaluation against test_answers.json.

    Args:
        note:        Label for this run (e.g. "baseline", "after few-shot prompt")
        limit:       If > 0, only evaluate first N questions (for smoke tests)
        top_k:       Number of chunks to retrieve per query
        judge_model: Model to use for judging (default: gpt-4o)
    """
    test_file = PROJECT_ROOT / "data" / "evaluation" / "test_answers.json"
    test_data = json.loads(test_file.read_text(encoding="utf-8"))

    if limit > 0:
        test_data = test_data[:limit]

    total = len(test_data)
    logger.info("Starting E2E eval: %d questions, top_k=%d, judge=%s, note='%s'",
                total, top_k, judge_model, note)

    rag = RAGPipeline(top_k=top_k)
    judge = Judge(model=judge_model)
    conn = get_connection()

    results = []
    correctness_total = 0
    faithfulness_total = 0
    total_rag_tokens = 0
    total_judge_tokens = 0

    print(f"\nE2E Evaluation — {total} questions\n")
    print(f"{'#':>3}  {'C':>2}  {'F':>2}  {'ms':>5}  Query")
    print(f"{'':>3}  {'':>2}  {'':>2}  {'':>5}  {'-' * 55}")

    for i, item in enumerate(test_data, 1):
        query_id = item["id"]
        query = item["query"]
        expected_answer = item["expected_answer"]
        answer_type = item["answer_type"]
        department = item["department"]

        print(f"\r  running {i}/{total}...", end="", flush=True)

        # Step 1: RAG
        rag_result = rag.ask(query)
        generated_answer = rag_result["answer"]
        chunks = rag_result["chunks"]
        latency_ms = rag_result["latency_ms"]
        rag_tokens = rag_result["prompt_tokens"] + rag_result["response_tokens"]

        # Step 2: Judge
        judgment = judge.evaluate(
            query=query,
            expected_answer=expected_answer,
            generated_answer=generated_answer,
            answer_type=answer_type,
            chunks=chunks,
        )
        correctness = judgment["correctness"]
        faithfulness = judgment["faithfulness"]
        judge_tokens = judgment["judge_tokens"]

        correctness_total += correctness
        faithfulness_total += faithfulness
        total_rag_tokens += rag_tokens
        total_judge_tokens += judge_tokens

        # Step 3: Persist
        conn.execute(
            """INSERT INTO e2e_eval_runs
               (run_note, query_id, query, answer_type, department,
                generated_answer, expected_answer,
                correctness, faithfulness,
                correctness_reasoning, faithfulness_reasoning,
                chunks_used, latency_ms, rag_tokens, judge_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                note, query_id, query, answer_type, department,
                generated_answer, expected_answer,
                correctness, faithfulness,
                judgment["correctness_reasoning"],
                judgment["faithfulness_reasoning"],
                len(chunks), latency_ms, rag_tokens, judge_tokens,
            ),
        )
        conn.commit()

        results.append(judgment | {"query": query, "answer_type": answer_type})

        # Per-query output (overwrite progress line)
        print(f"\r{i:>3}  {correctness:>2}  {faithfulness:>2}  {latency_ms:>5}  {query[:55]}")
        if correctness < 3:
            print(f"     Expected:   {expected_answer[:100]}")
            print(f"     Generated:  {generated_answer[:100]}")
            print(f"     Reasoning:  {judgment['correctness_reasoning'][:100]}")

    conn.close()

    # Summary
    avg_correctness = correctness_total / total
    avg_faithfulness = faithfulness_total / total
    pass_rate = sum(1 for r in results if r["correctness"] == 3) / total

    # Breakdown by answer type
    by_type: dict[str, list] = {}
    for r in results:
        by_type.setdefault(r["answer_type"], []).append(r["correctness"])

    print(f"\n{'═' * 60}")
    print(f"  E2E EVALUATION RESULTS")
    print(f"{'═' * 60}")
    if note:
        print(f"  Note:              {note}")
    print(f"  Questions:         {total}")
    print(f"  Avg Correctness:   {avg_correctness:.2f} / 3.0")
    print(f"  Avg Faithfulness:  {avg_faithfulness:.2f} / 3.0")
    print(f"  Pass rate (C=3):   {pass_rate:.1%}  ({sum(1 for r in results if r['correctness'] == 3)}/{total})")
    print(f"  RAG tokens:        {total_rag_tokens:,}")
    print(f"  Judge tokens:      {total_judge_tokens:,}")
    print(f"\n  By answer type:")
    for atype, scores in sorted(by_type.items()):
        avg = sum(scores) / len(scores)
        passes = sum(1 for s in scores if s == 3)
        print(f"    {atype:<15} avg={avg:.2f}  pass={passes}/{len(scores)}")
    print(f"{'═' * 60}\n")

    logger.info(
        "E2E eval complete: avg_correctness=%.2f, avg_faithfulness=%.2f, pass_rate=%.1f%%",
        avg_correctness, avg_faithfulness, pass_rate * 100,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--note", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--judge-model", default="gpt-4o")
    args = parser.parse_args()

    run(
        note=args.note,
        limit=args.limit,
        top_k=args.top_k,
        judge_model=args.judge_model,
    )
