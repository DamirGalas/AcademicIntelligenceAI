import json
import pickle
import sqlite3
from pathlib import Path

import faiss
import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

from academic_intelligence_ai.monitoring.logger import get_logger
from academic_intelligence_ai.monitoring.pipeline_tracker import PipelineTracker

logger = get_logger("load.load_documents")

# Project root: 4 levels up (load -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database with documents and chunks tables."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Drop and recreate for clean schema on each full reload
    cur.execute("DROP TABLE IF EXISTS chunks")
    cur.execute("DROP TABLE IF EXISTS documents")

    cur.execute("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            purpose TEXT NOT NULL,
            raw_filename TEXT NOT NULL,
            full_text_length INTEGER NOT NULL,
            processed_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            chunk_length INTEGER NOT NULL,
            char_offset INTEGER NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents(id)
        )
    """)

    conn.commit()
    return conn


def run():
    """Load all chunked JSON files into SQLite and FAISS."""
    with PipelineTracker("load") as tracker:
        config = load_config()

        embedding_cfg = config.get("embedding", {})
        vector_cfg = config.get("vector_db", {})
        model_name = embedding_cfg.get("model", "all-MiniLM-L6-v2")
        batch_size = embedding_cfg.get("batch_size", 32)

        db_path = PROJECT_ROOT / "data" / "academic.db"
        faiss_path = PROJECT_ROOT / vector_cfg.get("index_path", "data/embeddings/faiss_index")
        meta_path = faiss_path.parent / "metadata.pkl"

        chunked_dir = PROJECT_ROOT / config.get("paths", {}).get("chunked_data", "data/chunked/")
        json_files = list(chunked_dir.glob("*.json"))

        if not json_files:
            logger.warning("No chunked JSON files found in %s", chunked_dir)
            tracker.record(items_in=0, items_out=0, items_skipped=0)
            return

        logger.info("Found %d chunked file(s) to load", len(json_files))

        # Load embedding model
        logger.info("Loading embedding model: %s", model_name)
        model = SentenceTransformer(model_name)

        # Init DB (drops and recreates tables for clean schema)
        conn = init_db(db_path)
        cur = conn.cursor()

        all_texts = []
        metadata = []
        doc_count = 0

        for file_path in json_files:
            payload = json.loads(file_path.read_text(encoding="utf-8"))

            # Insert parent document
            cur.execute(
                "INSERT INTO documents (source, purpose, raw_filename, full_text_length, processed_at) VALUES (?, ?, ?, ?, ?)",
                (
                    payload["source"],
                    payload.get("purpose", "unknown"),
                    payload["raw_filename"],
                    payload["full_text_length"],
                    payload["processed_at"],
                ),
            )
            doc_id = cur.lastrowid
            doc_count += 1

            # Insert each chunk
            for chunk in payload["chunks"]:
                cur.execute(
                    "INSERT INTO chunks (doc_id, chunk_index, text, chunk_length, char_offset) VALUES (?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        chunk["chunk_index"],
                        chunk["text"],
                        chunk["chunk_length"],
                        chunk["char_offset"],
                    ),
                )
                chunk_id = cur.lastrowid

                all_texts.append(chunk["text"])
                metadata.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": chunk["chunk_index"],
                    "source": payload["source"],
                    "purpose": payload.get("purpose", "unknown"),
                })

            logger.info(
                "Loaded %s (doc_id=%d, %d chunks)",
                payload["source"], doc_id, len(payload["chunks"]),
            )

        conn.commit()

        # Detect empty or whitespace-only chunks
        empty_chunks = sum(1 for t in all_texts if not t.strip())
        if empty_chunks > 0:
            logger.warning("Detected %d empty/whitespace-only chunks", empty_chunks)
        tracker.add_metric("empty_chunks", empty_chunks)

        # Encode all chunks in batches with failure detection
        logger.info("Encoding %d chunks with %s (batch_size=%d)", len(all_texts), model_name, batch_size)
        dim = embedding_cfg.get("dimension", 384)
        all_embeddings = []
        embedding_failures = 0

        for i in range(0, len(all_texts), batch_size):
            batch_texts = all_texts[i : i + batch_size]
            try:
                batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
                all_embeddings.append(np.array(batch_embeddings).astype("float32"))
            except Exception as e:
                logger.error(
                    "Embedding failed for batch %d-%d: %s",
                    i, i + len(batch_texts), e,
                )
                embedding_failures += len(batch_texts)
                all_embeddings.append(np.zeros((len(batch_texts), dim), dtype="float32"))

        if embedding_failures > 0:
            logger.warning(
                "ALERT: %d chunks failed embedding (out of %d total)",
                embedding_failures, len(all_texts),
            )

        tracker.add_metric("embedding_failures", embedding_failures)
        tracker.add_metric("total_chunks_embedded", len(all_texts) - embedding_failures)

        embeddings_np = np.vstack(all_embeddings).astype("float32")

        # Build FAISS index (cosine similarity via normalized inner product)
        faiss.normalize_L2(embeddings_np)
        index = faiss.IndexFlatIP(embeddings_np.shape[1])
        index.add(embeddings_np)

        faiss_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(faiss_path))
        meta_path.write_bytes(pickle.dumps(metadata))

        logger.info(
            "Load complete: %d documents, %d chunks, %d vectors (dim=%d), DB=%s",
            doc_count, len(all_texts), index.ntotal, embeddings_np.shape[1], db_path.name,
        )

        tracker.record(
            items_in=len(json_files),
            items_out=len(all_texts) - embedding_failures,
            items_skipped=embedding_failures,
        )
        conn.close()


if __name__ == "__main__":
    run()
