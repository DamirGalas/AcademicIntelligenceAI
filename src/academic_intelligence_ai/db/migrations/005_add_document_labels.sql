-- Add category, relevance, and department labels to documents.
-- Populated by load/label_documents.py after the load pipeline runs.

ALTER TABLE documents ADD COLUMN category TEXT NOT NULL DEFAULT '';
ALTER TABLE documents ADD COLUMN relevance TEXT NOT NULL DEFAULT '';
ALTER TABLE documents ADD COLUMN department TEXT NOT NULL DEFAULT ''
