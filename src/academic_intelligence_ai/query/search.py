import pickle
import sqlite3
from pathlib import Path

import faiss
import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

from academic_intelligence_ai.monitoring.logger import get_logger

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

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Search for the most relevant chunks given a query string.

        Returns a list of dicts with keys: score, source, purpose, chunk_index, text.
        Results below confidence_threshold are filtered out.
        """
        if top_k is None:
            top_k = self.max_context_chunks

        # Encode and normalize query vector (index uses cosine via normalized IP)
        query_vector = self.model.encode(query).astype("float32")
        query_vector = np.expand_dims(query_vector, axis=0)
        faiss.normalize_L2(query_vector)

        distances, indices = self.index.search(query_vector, top_k)

        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue

            if score < self.confidence_threshold:
                logger.debug("Skipping chunk idx=%d, score=%.3f below threshold %.2f", idx, score, self.confidence_threshold)
                continue

            meta = self.metadata[idx]
            chunk_id = meta["chunk_id"]

            row = self.conn.execute(
                "SELECT text FROM chunks WHERE id = ?", (chunk_id,)
            ).fetchone()

            if not row:
                logger.warning("Chunk id=%d not found in database", chunk_id)
                continue

            results.append({
                "score": round(float(score), 4),
                "source": meta["source"],
                "purpose": meta.get("purpose", "unknown"),
                "chunk_index": meta["chunk_index"],
                "text": row[0],
            })

        logger.info(
            "Query: '%s' -> %d results (top_k=%d, threshold=%.2f)",
            query[:80], len(results), top_k, self.confidence_threshold,
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
            print(f"\n  [{i}] score={r['score']}  source={r['source']}  purpose={r['purpose']}")
            print(f"      {r['text'][:200]}...")

        print()


if __name__ == "__main__":
    run()
