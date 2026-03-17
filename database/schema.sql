-- Kafin — Supabase Tabellen-Schema

CREATE TABLE IF NOT EXISTS watchlist (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    company_name TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    added_date TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    cross_signal_tickers TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS short_term_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    source TEXT NOT NULL,
    bullet_points JSONB NOT NULL,
    sentiment_score FLOAT,
    category TEXT,
    quarter TEXT NOT NULL,
    is_material BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stm_ticker_quarter ON short_term_memory(ticker, quarter);

CREATE TABLE IF NOT EXISTS long_term_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    quarter TEXT NOT NULL,
    eps_actual FLOAT,
    eps_consensus FLOAT,
    eps_whisper FLOAT,
    revenue_actual FLOAT,
    revenue_consensus FLOAT,
    stock_reaction_1d FLOAT,
    stock_reaction_5d FLOAT,
    ki_recommendation TEXT,
    ki_opportunity_score FLOAT,
    ki_torpedo_score FLOAT,
    outcome_correct BOOLEAN,
    key_learnings TEXT,
    guidance_direction TEXT,
    core_metric_name TEXT,
    core_metric_trend TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ticker, quarter)
);
CREATE INDEX IF NOT EXISTS idx_ltm_ticker ON long_term_memory(ticker);

CREATE TABLE IF NOT EXISTS macro_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date TIMESTAMP NOT NULL,
    fed_rate FLOAT,
    fed_expectation TEXT,
    vix FLOAT,
    credit_spread_bps FLOAT,
    yield_curve TEXT,
    dxy FLOAT,
    regime TEXT,
    index_shorts_recommended BOOLEAN DEFAULT false,
    instrument_suggestions TEXT,
    geopolitical_notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS btc_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date TIMESTAMP NOT NULL,
    price FLOAT,
    price_7d_change_percent FLOAT,
    open_interest_usd FLOAT,
    open_interest_trend TEXT,
    funding_rate FLOAT,
    long_short_ratio FLOAT,
    liquidation_cluster_long FLOAT,
    liquidation_cluster_short FLOAT,
    dxy FLOAT,
    recommendation TEXT,
    reasoning TEXT,
    key_support FLOAT,
    key_resistance FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    report_date TIMESTAMP NOT NULL,
    earnings_date TIMESTAMP,
    opportunity_score FLOAT,
    torpedo_score FLOAT,
    recommendation TEXT,
    report_content TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    spy_price FLOAT,
    spy_change_pct FLOAT,
    qqq_price FLOAT,
    qqq_change_pct FLOAT,
    dia_price FLOAT,
    iwm_price FLOAT,
    vix FLOAT,
    credit_spread FLOAT,
    yield_spread FLOAT,
    dxy FLOAT,
    top_sector TEXT,
    bottom_sector TEXT,
    regime TEXT,
    briefing_summary TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_ticker ON audit_reports(ticker, report_date);
