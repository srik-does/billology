-- Search-enrichment tags for the Q&A retrieval paths (Ask reliability).
-- LLM-generated DESCRIPTIVE labels only (tags, merchant aliases) — never
-- figures (Principle I). Folded into the embedding text and matched as
-- keywords so small wording changes in a question no longer miss.
-- Backfill existing bills with: python backend/scripts/backfill_tags.py

ALTER TABLE bills ADD COLUMN IF NOT EXISTS tags text;
