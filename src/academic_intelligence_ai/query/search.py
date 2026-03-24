import pickle
import sqlite3
from pathlib import Path

import faiss
import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.utils.text import transliterate

logger = get_logger("query.search")

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


class Searcher:
    """Loads FAISS index, metadata and embedding model once, reuses across queries."""

    def __init__(self):
        config = load_config()

        embedding_cfg = config.get("embedding", {})
        vector_cfg = config.get("vector_db", {})
        query_cfg = config.get("query", {})

        model_name = embedding_cfg.get("model", "all-MiniLM-L6-v2")
        faiss_path = PROJECT_ROOT / vector_cfg.get("index_path", "data/embeddings/faiss_index")
        meta_path = faiss_path.parent / "metadata.pkl"
        db_path = PROJECT_ROOT / "data" / "academic.db"

        self.max_context_chunks = query_cfg.get("max_context_chunks", 5)
        self.confidence_threshold = query_cfg.get("confidence_threshold", 0.5)
        self.retrieval_multiplier = query_cfg.get("retrieval_multiplier", 3)
        self.high_relevance_boost = query_cfg.get("high_relevance_boost", 1.2)
        self.relevance_filter = True  # can be disabled for eval baselines
        self.exclude_pdfs = query_cfg.get("exclude_pdfs", True)
        self.allowed_categories: list[str] | None = query_cfg.get("allowed_categories", None)
        self.max_chunks_per_url = query_cfg.get("max_chunks_per_url", 2)

        logger.info("Loading embedding model: %s", model_name)
        self.model = SentenceTransformer(model_name)

        logger.info("Loading FAISS index from %s", faiss_path)
        self.index = faiss.read_index(str(faiss_path))

        self.metadata = pickle.loads(meta_path.read_bytes())
        self.conn = sqlite3.connect(db_path)

        logger.info(
            "Searcher ready: %d vectors, %d metadata entries",
            self.index.ntotal, len(self.metadata),
        )

    def search(self, query: str, top_k: int | None = None, category_filter: str | None = None) -> list[dict]:
        """Search for the most relevant chunks given a query string.

        Returns a list of dicts with keys: score, source, purpose, chunk_index, text.
        Results below confidence_threshold are filtered out.
        """
        if top_k is None:
            top_k = self.max_context_chunks

        # Fetch more candidates to account for post-filter removals.
        # When PDFs are excluded (~89% of index), multiply aggressively to
        # ensure enough HTML candidates survive the filter.
        fetch_k = top_k * self.retrieval_multiplier
        if self.exclude_pdfs:
            fetch_k = max(fetch_k * 10, 300)

        # Transliterate Cyrillic to Latin (index is stored in Latin)
        # then apply E5 "query: " prefix before encoding
        query_vector = self.model.encode(f"query: {transliterate(query)}").astype("float32")
        query_vector = np.expand_dims(query_vector, axis=0)
        faiss.normalize_L2(query_vector)

        distances, indices = self.index.search(query_vector, fetch_k)

        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue

            if score < self.confidence_threshold:
                logger.debug("Skipping chunk idx=%d, score=%.3f below threshold %.2f", idx, score, self.confidence_threshold)
                continue

            meta = self.metadata[idx]

            if self.exclude_pdfs and meta.get("file_type") == "pdf":
                continue

            chunk_id = meta["chunk_id"]
            doc_id = meta["doc_id"]

            # Look up relevance and category — filter and boost
            doc_row = self.conn.execute(
                "SELECT relevance, category FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
            relevance = doc_row[0] if doc_row else "none"
            category = doc_row[1] if doc_row else ""

            if self.relevance_filter and relevance == "none":
                continue

            effective_categories = [category_filter] if category_filter else self.allowed_categories
            if effective_categories is not None and category not in effective_categories:
                continue

            boosted_score = score * self.high_relevance_boost if relevance == "high" else score

            row = self.conn.execute(
                "SELECT text FROM chunks WHERE id = ?", (chunk_id,)
            ).fetchone()

            if not row:
                logger.warning("Chunk id=%d not found in database", chunk_id)
                continue

            results.append({
                "score": round(float(boosted_score), 4),
                "source": meta["source"],
                "url": meta.get("url", ""),
                "relevance": relevance,
                "chunk_index": meta.get("chunk_index", -1),
                "text": row[0],
            })

        # Deduplicate by URL — keep top N chunks per page
        seen_urls: dict[str, list] = {}
        for r in results:
            url = r["url"]
            chunks = seen_urls.setdefault(url, [])
            if len(chunks) < self.max_chunks_per_url:
                chunks.append(r)
        results = [r for chunks in seen_urls.values() for r in chunks]

        # Re-sort after boosting and deduplication, trim to requested top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        results = results[:top_k]

        logger.info(
            "Query: '%s' -> %d results (fetch_k=%d, top_k=%d, threshold=%.2f)",
            query[:80], len(results), fetch_k, top_k, self.confidence_threshold,
        )
        return results


def run():
    """Interactive search loop for testing."""
    searcher = Searcher()
    print("\nSearch ready. Type a query (or 'q' to quit).\n")

    while True:
        query = input("Query: ").strip()
        if not query or query.lower() == "q":
            break

        results = searcher.search(query)

        if not results:
            print("  No results above confidence threshold.\n")
            continue

        for i, r in enumerate(results, 1):
            print(f"\n  [{i}] score={r['score']}  source={r['source']}  url={r['url']}")
            print(f"      {r['text'][:200]}...")

        print()


if __name__ == "__main__":
    run()
