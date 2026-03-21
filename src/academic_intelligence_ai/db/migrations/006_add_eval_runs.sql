-- Retrieval evaluation run history.
-- Each row is one benchmark run with the active filter settings and aggregate metrics.

CREATE TABLE IF NOT EXISTS eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL DEFAULT (datetime('now')),
    benchmark_file TEXT NOT NULL,
    top_k INTEGER NOT NULL,
    confidence_threshold REAL NOT NULL,
    relevance_filter INTEGER NOT NULL,  -- 1 = enabled, 0 = disabled
    total_queries INTEGER NOT NULL,
    precision_at_1 REAL NOT NULL,
    precision_at_3 REAL NOT NULL,
    fragment_hit REAL NOT NULL,
    mrr REAL NOT NULL,
    avg_hit_score REAL NOT NULL,
    avg_miss_score REAL NOT NULL,
    note TEXT NOT NULL DEFAULT ''
)
