import json
import pickle
import sqlite3
from pathlib import Path

import faiss
import numpy as np
import yaml
from sentence_transformers import SentenceTransformer

from academic_intelligence_ai.monitoring.logger import get_logger

logger = get_logger("load.load_documents")

# Project root: 4 levels up (load -> academic_intelligence_ai -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_config() -> dict:
    """Load configuration from config/config.yaml."""
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def init_db(db_path: Path) -> sqlite3.Connection:
    """Create SQLite database and documents table."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            purpose TEXT NOT NULL,
            raw_filename TEXT NOT NULL,
            text TEXT NOT NULL,
            text_length INTEGER NOT NULL,
            processed_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def clear_db(conn: sqlite3.Connection):
    """Remove all existing documents before a fresh load."""
    conn.execute("DELETE FROM documents")
    conn.commit()


def run():
    """Load all processed JSON files into SQLite and FAISS."""
    config = load_config()

    embedding_cfg = config.get("embedding", {})
    vector_cfg = config.get("vector_db", {})
    model_name = embedding_cfg.get("model", "all-MiniLM-L6-v2")

    db_path = PROJECT_ROOT / "data" / "academic.db"
    faiss_path = PROJECT_ROOT / vector_cfg.get("index_path", "data/embeddings/faiss_index")
    meta_path = faiss_path.parent / "metadata.pkl"

    processed_dir = PROJECT_ROOT / "data" / "processed"
    json_files = list(processed_dir.glob("*.json"))

    if not json_files:
        logger.warning("No processed JSON files found in %s", processed_dir)
        return

    logger.info("Found %d processed file(s) to load", len(json_files))

    # Load embedding model
    logger.info("Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)

    # Init and clear DB for fresh load
    conn = init_db(db_path)
    clear_db(conn)
    cur = conn.cursor()

    embeddings = []
    metadata = []

    for file_path in json_files:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        text = payload["text"]
        meta = payload["metadata"]

        cur.execute(
            "INSERT INTO documents (source, purpose, raw_filename, text, text_length, processed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (meta["source"], meta.get("purpose", "unknown"), meta["raw_filename"], text, meta["text_length"], meta["processed_at"]),
        )
        doc_id = cur.lastrowid

        vector = model.encode(text)
        embeddings.append(vector)
        metadata.append({
            "doc_id": doc_id,
            "source": meta["source"],
            "purpose": meta.get("purpose", "unknown"),
        })

        logger.info("Loaded %s (doc_id=%d, %d chars)", meta["source"], doc_id, meta["text_length"])

    conn.commit()

    # Build FAISS index (cosine similarity via normalized inner product)
    embeddings_np = np.vstack(embeddings).astype("float32")
    faiss.normalize_L2(embeddings_np)
    index = faiss.IndexFlatIP(embeddings_np.shape[1])
    index.add(embeddings_np)

    faiss_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(faiss_path))
    meta_path.write_bytes(pickle.dumps(metadata))

    logger.info(
        "Load complete: %d documents, %d vectors (dim=%d), DB=%s",
        len(json_files), index.ntotal, embeddings_np.shape[1], db_path.name,
    )


if __name__ == "__main__":
    run()
