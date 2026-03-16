-- Pipeline run tracking (migrated from pipeline_tracker.py)

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    step TEXT NOT NULL,
    duration_sec REAL NOT NULL,
    items_in INTEGER NOT NULL,
    items_out INTEGER NOT NULL,
    items_skipped INTEGER NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
)