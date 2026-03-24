CREATE TABLE IF NOT EXISTS e2e_eval_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_note TEXT NOT NULL DEFAULT '',
    query_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    answer_type TEXT NOT NULL,
    department TEXT NOT NULL,
    generated_answer TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    correctness INTEGER NOT NULL,
    faithfulness INTEGER NOT NULL,
    correctness_reasoning TEXT NOT NULL DEFAULT '',
    faithfulness_reasoning TEXT NOT NULL DEFAULT '',
    chunks_used INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    rag_tokens INTEGER NOT NULL DEFAULT 0,
    judge_tokens INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)
