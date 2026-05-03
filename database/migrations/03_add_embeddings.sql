-- Migration Script for pgvector Embedding Support
-- Run this manually on existing databases after K6-4 deployment

-- Add embedding columns if they don't exist
ALTER TABLE short_term_memory
    ADD COLUMN IF NOT EXISTS embedding vector(384);

ALTER TABLE long_term_memory
    ADD COLUMN IF NOT EXISTS embedding vector(384);

ALTER TABLE audit_reports
    ADD COLUMN IF NOT EXISTS embedding vector(384);

-- Create HNSW indexes for fast vector search
CREATE INDEX IF NOT EXISTS idx_stm_embedding
    ON short_term_memory
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_ltm_embedding
    ON long_term_memory
    USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_audit_embedding
    ON audit_reports
    USING hnsw (embedding vector_cosine_ops);

-- Grant permissions (adjust user as needed)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO kafin;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO kafin;
