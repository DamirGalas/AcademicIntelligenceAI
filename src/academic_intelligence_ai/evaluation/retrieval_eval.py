import json
from pathlib import Path

from academic_intelligence_ai.db.connection import get_connection
from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.query.search import Searcher

logger = get_logger("evaluation.retrieval_eval")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def evaluate(
    test_file: Path,
    top_k: int = 5,
    confidence_threshold: float | None = None,
    relevance_filter: bool = True,
    note: str = "",
):
    """Run retrieval evaluation against a test set.

    Measures:
      - Precision@1: correct source at rank 1
      - Precision@3: correct source in top 3
      - Hit@K (fragment): expected text fragment found in any top-K result
      - MRR: Mean Reciprocal Rank (by source)
      - Average score for hits vs misses

    Results are persisted to the eval_runs table in SQLite.

    Args:
        confidence_threshold: Override config value. Pass 0.0 to disable.
        relevance_filter: If False, skips the relevance='none' filter in search.
        note: Free-text label for this run (e.g. "baseline no filters").
    """
    searcher = Searcher()

    # Apply overrides
    if confidence_threshold is not None:
        searcher.confidence_threshold = confidence_threshold
    if not relevance_filter:
        searcher.relevance_filter = False

    test_data = json.loads(test_file.read_text(encoding="utf-8"))
    total = len(test_data)

    correct_at_1 = 0
    correct_at_3 = 0
    correct_at_9 = 0
    correct_at_30 = 0
    fragment_hits = 0
    mrr_total = 0.0
    hit_scores: list[float] = []
    miss_scores: list[float] = []

    fetch_k = max(top_k, 30)

    print(f"\nEvaluating {total} queries (top_k={top_k})\n")
    print(f"{'#':>3}  {'P@1':>4}  {'Frag':>4}  {'Score':>6}  Query")
    print(f"{'':>3}  {'':>4}  {'':>4}  {'':>6}  {'-' * 50}")

    for i, item in enumerate(test_data):
        query = item["query"]
        expected_source = item["expected_source"]
        expected_fragment = item.get("expected_text_fragment", "")

        results = searcher.search(query, top_k=fetch_k)
        urls = [r["url"] for r in results]
        top_score = results[0]["score"] if results else 0.0

        # Precision@1: expected URL matches rank-1 result
        p1 = urls[0] == expected_source if urls else False
        if p1:
            correct_at_1 += 1

        # Precision@3
        if expected_source in urls[:3]:
            correct_at_3 += 1

        # Precision@9
        if expected_source in urls[:9]:
            correct_at_9 += 1

        # Precision@30
        if expected_source in urls[:30]:
            correct_at_30 += 1

        # Fragment hit: check if expected text appears in any result
        frag_hit = any(expected_fragment in r["text"] for r in results) if expected_fragment else False
        if frag_hit:
            fragment_hits += 1
            hit_scores.append(top_score)
        else:
            miss_scores.append(top_score)

        # MRR
        if expected_source in urls:
            rank = urls.index(expected_source) + 1
            mrr_total += 1.0 / rank

        # Per-query output
        p1_mark = "Y" if p1 else "-"
        frag_mark = "Y" if frag_hit else "MISS"
        print(f"{i+1:>3}  {p1_mark:>4}  {frag_mark:>4}  {top_score:>6.3f}  {query}")

        # Failure detail: show returned URLs vs expected
        if not p1 or not frag_hit:
            got_top3 = [f"{r['url']}({r['score']:.2f})" for r in results[:3]]
            print(f"     >> expected={expected_source}")
            print(f"     >> got=[{', '.join(got_top3)}]")

    # Summary
    precision_1 = correct_at_1 / total
    precision_3 = correct_at_3 / total
    precision_9 = correct_at_9 / total
    precision_30 = correct_at_30 / total
    fragment_rate = fragment_hits / total
    mrr = mrr_total / total
    avg_hit_score = sum(hit_scores) / len(hit_scores) if hit_scores else 0.0
    avg_miss_score = sum(miss_scores) / len(miss_scores) if miss_scores else 0.0

    active_threshold = searcher.confidence_threshold
    active_relevance = getattr(searcher, "relevance_filter", True)

    print(f"\n{'═' * 60}")
    print(f"  RETRIEVAL EVALUATION RESULTS")
    print(f"{'═' * 60}")
    print(f"  Benchmark:           {test_file.name}")
    print(f"  Confidence thresh:   {active_threshold}")
    print(f"  Relevance filter:    {'on' if active_relevance else 'off'}")
    if note:
        print(f"  Note:                {note}")
    print(f"  Queries:             {total}")
    print(f"  Precision@1:         {precision_1:.1%}  ({correct_at_1}/{total})")
    print(f"  Precision@3:         {precision_3:.1%}  ({correct_at_3}/{total})")
    print(f"  Precision@9:         {precision_9:.1%}  ({correct_at_9}/{total})")
    print(f"  Precision@30:        {precision_30:.1%}  ({correct_at_30}/{total})")
    print(f"  Fragment Hit@{top_k}:     {fragment_rate:.1%}  ({fragment_hits}/{total})")
    print(f"  MRR:                 {mrr:.3f}")
    print(f"  Avg score (hits):    {avg_hit_score:.3f}")
    print(f"  Avg score (misses):  {avg_miss_score:.3f}")
    print(f"{'═' * 60}\n")

    logger.info(
        "Evaluation: P@1=%.1f%%, P@3=%.1f%%, FragHit=%.1f%%, MRR=%.3f",
        precision_1 * 100, precision_3 * 100, fragment_rate * 100, mrr,
    )

    # Persist to DB
    conn = get_connection()
    conn.execute(
        """INSERT INTO eval_runs
           (benchmark_file, top_k, confidence_threshold, relevance_filter,
            total_queries, precision_at_1, precision_at_3, precision_at_9,
            precision_at_30, fragment_hit, mrr, avg_hit_score, avg_miss_score, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            test_file.name,
            top_k,
            active_threshold,
            1 if active_relevance else 0,
            total,
            round(precision_1, 4),
            round(precision_3, 4),
            round(precision_9, 4),
            round(precision_30, 4),
            round(fragment_rate, 4),
            round(mrr, 4),
            round(avg_hit_score, 4),
            round(avg_miss_score, 4),
            note,
        ),
    )
    conn.commit()
    conn.close()
    logger.info("Eval run saved to DB")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", default="benchmark.json")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.0)
    parser.add_argument("--relevance-filter", action="store_true")
    parser.add_argument("--note", default="baseline: no filters")
    args = parser.parse_args()

    test_file = PROJECT_ROOT / "data" / "evaluation" / args.benchmark
    evaluate(
        test_file,
        top_k=args.top_k,
        confidence_threshold=args.threshold,
        relevance_filter=args.relevance_filter,
        note=args.note,
    )
