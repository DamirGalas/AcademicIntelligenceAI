-- Per-domain, per-filter breakdown for each pipeline run

CREATE TABLE filter_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    file_type TEXT NOT NULL,
    reason TEXT NOT NULL,
    count INTEGER NOT NULL,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
)