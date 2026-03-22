-- API Usage Tracking
-- Täglich aggregierte Zähler pro API + Modell

CREATE TABLE IF NOT EXISTS api_usage (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date        DATE NOT NULL DEFAULT CURRENT_DATE,
    api_name    TEXT NOT NULL,   -- 'deepseek', 'groq', 'fmp', 'finnhub', 'fred'
    model       TEXT,            -- 'deepseek-chat', 'deepseek-reasoner', 'llama-3.1-8b-instant'
    call_count  INTEGER NOT NULL DEFAULT 0,
    input_tokens  BIGINT DEFAULT 0,
    output_tokens BIGINT DEFAULT 0,
    total_tokens  BIGINT DEFAULT 0,
    estimated_cost_usd NUMERIC(10, 6) DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(date, api_name, model)
);

CREATE INDEX IF NOT EXISTS idx_api_usage_date
    ON api_usage(date DESC, api_name);
