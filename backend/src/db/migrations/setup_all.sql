-- ============================================================================
-- Billology — full schema setup (migrations 001–005, in order).
-- Paste this whole file once into the Supabase SQL editor of the SAME project
-- your deployed backend points at (its SUPABASE_URL). Every statement is
-- idempotent, so re-running it is safe even if some objects already exist.
-- This is a convenience concatenation; the individual 00N_*.sql files remain
-- the source of truth.
-- ============================================================================


-- ============================================================================
-- 001_init.sql — initial schema (data-model.md)
-- Single canonical record per bill (Principle III). Money as numeric(14,2);
-- every value-bearing field carries provenance + source trace.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()

-- Categories (controlled list) ------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name       text NOT NULL,
    is_seeded  boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX IF NOT EXISTS categories_name_lower_idx
    ON categories (lower(name));

-- Bills (canonical record) ----------------------------------------------------
CREATE TABLE IF NOT EXISTS bills (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant            text,
    merchant_provenance text,
    merchant_source_ref jsonb,
    merchant_confidence real,
    bill_type           text NOT NULL DEFAULT 'unsupported',
    bill_date           date,
    bill_date_provenance text,
    bill_date_source_ref jsonb,
    bill_date_confidence real,
    currency            text NOT NULL DEFAULT 'INR',
    subtotal            numeric(14,2),
    tax_rate            numeric(6,3),
    tax_base            numeric(14,2),
    tax_amount          numeric(14,2),
    total_amount        numeric(14,2) NOT NULL,
    total_provenance    text,
    total_source_ref    jsonb,
    total_confidence    real,
    category_id         uuid REFERENCES categories (id),
    category_provenance text,
    layout_supported    boolean NOT NULL DEFAULT true,
    nothing_to_verify   boolean NOT NULL DEFAULT false,
    status              text NOT NULL DEFAULT 'candidate',
    embedding           vector(384),
    created_at          timestamptz NOT NULL DEFAULT now(),
    saved_at            timestamptz
);

CREATE INDEX IF NOT EXISTS bills_dup_idx
    ON bills (merchant, bill_date, total_amount);
CREATE INDEX IF NOT EXISTS bills_category_idx ON bills (category_id);
CREATE INDEX IF NOT EXISTS bills_date_idx ON bills (bill_date);
CREATE INDEX IF NOT EXISTS bills_embedding_idx
    ON bills USING hnsw (embedding vector_cosine_ops);

-- Line items ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS line_items (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id              uuid NOT NULL REFERENCES bills (id) ON DELETE CASCADE,
    position             int NOT NULL,
    description          text,
    description_provenance text,
    description_source_ref jsonb,
    description_confidence real,
    quantity             numeric(12,3),
    unit_amount          numeric(14,2),
    line_total           numeric(14,2) NOT NULL,
    line_total_provenance text,
    line_total_source_ref jsonb,
    line_total_confidence real
);
CREATE INDEX IF NOT EXISTS line_items_bill_idx ON line_items (bill_id);

-- Source artifacts ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_artifacts (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id       uuid NOT NULL REFERENCES bills (id) ON DELETE CASCADE,
    kind          text NOT NULL,
    storage_path  text,
    page_order    int NOT NULL DEFAULT 0,
    raw_text      text,
    quality_score real
);
CREATE INDEX IF NOT EXISTS source_artifacts_bill_idx ON source_artifacts (bill_id);

-- Discrepancy flags -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS discrepancy_flags (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id             uuid NOT NULL REFERENCES bills (id) ON DELETE CASCADE,
    kind                text NOT NULL,
    conflicting_figures jsonb NOT NULL,
    explanation_text    text
);
CREATE INDEX IF NOT EXISTS discrepancy_flags_bill_idx ON discrepancy_flags (bill_id);

-- Explanations ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS explanations (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id           uuid NOT NULL REFERENCES bills (id) ON DELETE CASCADE,
    bill_summary      text,
    line_explanations jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS explanations_bill_idx ON explanations (bill_id);


-- ============================================================================
-- 002_seed_categories.sql — controlled category list (FR-013).
-- ============================================================================

INSERT INTO categories (name, is_seeded) VALUES
    ('Telecom/Recharge', true),
    ('Groceries', true),
    ('Utilities', true),
    ('Food & Dining', true),
    ('Shopping', true),
    ('Other', true)
ON CONFLICT (lower(name)) DO NOTHING;


-- ============================================================================
-- 003_match_bills.sql — semantic-search RPC (Q&A semantic path).
-- pgvector's <=> is cosine distance (smaller = more similar).
-- ============================================================================

CREATE OR REPLACE FUNCTION match_bills(query_embedding vector(384), match_count int)
RETURNS TABLE (
    id uuid,
    merchant text,
    bill_date date,
    total_amount numeric,
    category_id uuid,
    distance double precision
)
LANGUAGE sql STABLE AS $$
    SELECT b.id, b.merchant, b.bill_date, b.total_amount, b.category_id,
           (b.embedding <=> query_embedding) AS distance
    FROM bills b
    WHERE b.status = 'saved' AND b.embedding IS NOT NULL
    ORDER BY b.embedding <=> query_embedding
    LIMIT match_count;
$$;


-- ============================================================================
-- 004_bill_tags.sql — search-enrichment tags for Q&A retrieval.
-- Backfill existing bills with: python backend/scripts/backfill_tags.py
-- ============================================================================

ALTER TABLE bills ADD COLUMN IF NOT EXISTS tags text;


-- ============================================================================
-- 005_tax_lines.sql — per-component tax breakdown (CGST/SGST/IGST/Cess/VAT/…).
-- The canonical summed figure stays on bills.tax_amount; these rows are the
-- named breakdown shown after the subtotal. ``name`` is free text.
-- ============================================================================

CREATE TABLE IF NOT EXISTS tax_lines (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bill_id           uuid NOT NULL REFERENCES bills (id) ON DELETE CASCADE,
    position          int NOT NULL,
    name              text NOT NULL,
    rate              numeric(6,3),
    amount            numeric(14,2) NOT NULL,
    amount_provenance text,
    amount_source_ref jsonb,
    amount_confidence real
);
CREATE INDEX IF NOT EXISTS tax_lines_bill_idx ON tax_lines (bill_id);
