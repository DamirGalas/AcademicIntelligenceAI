import json
from pathlib import Path

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.search import Searcher

logger = get_logger("evaluation.retrieval_eval")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def evaluate(test_file: Path, top_k: int = 5):
    """Run retrieval evaluation against a test set.

    Measures:
      - Precision@1: correct source at rank 1
      - Precision@3: correct source in top 3
      - Hit@K (fragment): expected text fragment found in any top-K result
      - MRR: Mean Reciprocal Rank (by source)
      - Average score for hits vs misses
    """
    searcher = Searcher()

    test_data = json.loads(test_file.read_text(encoding="utf-8"))
    total = len(test_data)

    correct_at_1 = 0
    correct_at_3 = 0
    fragment_hits = 0
    mrr_total = 0.0
    hit_scores: list[float] = []
    miss_scores: list[float] = []

    print(f"\nEvaluating {total} queries (top_k={top_k})\n")
    print(f"{'#':>3}  {'P@1':>4}  {'Frag':>4}  {'Score':>6}  Query")
    print(f"{'':>3}  {'':>4}  {'':>4}  {'':>6}  {'─' * 50}")

    for i, item in enumerate(test_data):
        query = item["query"]
        expected_source = item["expected_source"]
        expected_fragment = item.get("expected_text_fragment", "")

        results = searcher.search(query, top_k=top_k)
        sources = [r["source"] for r in results]
        top_score = results[0]["score"] if results else 0.0

        # Precision@1
        p1 = sources[0] == expected_source if sources else False
        if p1:
            correct_at_1 += 1

        # Precision@3
        if expected_source in sources[:3]:
            correct_at_3 += 1

        # Fragment hit: check if expected text appears in any result
        frag_hit = any(expected_fragment in r["text"] for r in results) if expected_fragment else False
        if frag_hit:
            fragment_hits += 1
            hit_scores.append(top_score)
        else:
            miss_scores.append(top_score)

        # MRR
        if expected_source in sources:
            rank = sources.index(expected_source) + 1
            mrr_total += 1.0 / rank

        # Per-query output
        p1_mark = "Y" if p1 else "-"
        frag_mark = "Y" if frag_hit else "MISS"
        print(f"{i+1:>3}  {p1_mark:>4}  {frag_mark:>4}  {top_score:>6.3f}  {query}")

        # Failure detail: show what was returned vs expected
        if not p1 or not frag_hit:
            got_top3 = [f"{r['source']}({r['score']:.2f})" for r in results[:3]]
            print(f"     >> expected={expected_source}  got=[{', '.join(got_top3)}]")

    # Summary
    precision_1 = correct_at_1 / total
    precision_3 = correct_at_3 / total
    fragment_rate = fragment_hits / total
    mrr = mrr_total / total
    avg_hit_score = sum(hit_scores) / len(hit_scores) if hit_scores else 0.0
    avg_miss_score = sum(miss_scores) / len(miss_scores) if miss_scores else 0.0

    print(f"\n{'═' * 60}")
    print(f"  RETRIEVAL EVALUATION RESULTS")
    print(f"{'═' * 60}")
    print(f"  Queries:             {total}")
    print(f"  Precision@1:         {precision_1:.1%}  ({correct_at_1}/{total})")
    print(f"  Precision@3:         {precision_3:.1%}  ({correct_at_3}/{total})")
    print(f"  Fragment Hit@{top_k}:     {fragment_rate:.1%}  ({fragment_hits}/{total})")
    print(f"  MRR:                 {mrr:.3f}")
    print(f"  Avg score (hits):    {avg_hit_score:.3f}")
    print(f"  Avg score (misses):  {avg_miss_score:.3f}")
    print(f"{'═' * 60}\n")

    logger.info(
        "Evaluation: P@1=%.1f%%, P@3=%.1f%%, FragHit=%.1f%%, MRR=%.3f",
        precision_1 * 100, precision_3 * 100, fragment_rate * 100, mrr,
    )


if __name__ == "__main__":
    test_file = PROJECT_ROOT / "data" / "evaluation" / "test_queries.json"
    evaluate(test_file)
