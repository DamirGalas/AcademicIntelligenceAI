from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import CrossEncoder

from academic_intelligence_ai.monitoring.logger import get_logger

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

logger = get_logger("query.reranker")


class Reranker:
    """Cross-encoder re-ranker for second-stage retrieval scoring."""

    def __init__(self, model_name: str):
        logger.info("Loading cross-encoder model: %s", model_name)
        self.model = CrossEncoder(model_name)
        logger.info("Cross-encoder ready")

    def rerank(self, query: str, results: list[dict], top_k: int) -> list[dict]:
        """Re-rank results using cross-encoder scores.

        Takes a list of candidate chunks, scores each (query, chunk) pair,
        and returns top_k sorted by cross-encoder score descending.
        """
        if not results:
            return results

        pairs = [(query, r["text"]) for r in results]
        scores = self.model.predict(pairs)

        for r, score in zip(results, scores):
            r["rerank_score"] = round(float(score), 4)

        reranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)

        logger.info(
            "Re-ranked %d candidates -> top %d (best=%.4f, worst=%.4f)",
            len(results), top_k,
            reranked[0]["rerank_score"] if reranked else 0,
            reranked[top_k - 1]["rerank_score"] if len(reranked) >= top_k else 0,
        )

        return reranked[:top_k]
