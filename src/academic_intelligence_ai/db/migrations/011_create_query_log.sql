-- Log of all queries submitted through the web interface.
-- One row per user query.

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    num_chunks INTEGER NOT NULL DEFAULT 0,
    top_chunk_url TEXT NOT NULL DEFAULT '',
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    response_tokens INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0
)
