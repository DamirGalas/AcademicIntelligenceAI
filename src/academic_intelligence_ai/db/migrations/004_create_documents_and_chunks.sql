-- Document and chunk storage for the load pipeline.
-- These tables hold the current state (full reload on each run).
-- Metrics/history are in pipeline_runs + run_metrics (never deleted).

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    file_type TEXT NOT NULL DEFAULT '',
    raw_filename TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    full_text_length INTEGER NOT NULL,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    chunk_length INTEGER NOT NULL,
    char_offset INTEGER NOT NULL,
    chunk_size INTEGER NOT NULL,
    chunk_overlap INTEGER NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(id)
)
