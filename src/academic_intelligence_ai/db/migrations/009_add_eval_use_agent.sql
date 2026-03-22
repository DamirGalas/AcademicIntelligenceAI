-- Track whether a retrieval eval run used LLM query rewriting (agent mode).

ALTER TABLE eval_runs ADD COLUMN use_agent INTEGER NOT NULL DEFAULT 0
