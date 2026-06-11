-- Semantic search RPC for the Q&A semantic path (Phase 8 / US9).
-- Returns saved bills ordered by cosine distance to the query embedding.
-- pgvector's <=> is cosine distance (smaller = more similar).

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
