-- Add Precision@30 metric to eval_runs.

ALTER TABLE eval_runs ADD COLUMN precision_at_30 REAL NOT NULL DEFAULT 0.0
