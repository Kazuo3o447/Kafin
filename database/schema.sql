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

-- Langzeit-Gedächtnis für persistente Ticker-Erkenntnisse
CREATE TABLE IF NOT EXISTS long_term_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    category TEXT NOT NULL,
    insight TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.5,
    source TEXT,
    quarter TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
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
    report_type TEXT DEFAULT 'audit',
    report_date TIMESTAMP,
    earnings_date TIMESTAMP,
    opportunity_score FLOAT,
    torpedo_score FLOAT,
    recommendation TEXT,
    report_text TEXT,
    prompt_version TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Post-Earnings Reviews
CREATE TABLE IF NOT EXISTS earnings_reviews (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    quarter TEXT NOT NULL,
    pre_earnings_score_opportunity FLOAT,
    pre_earnings_score_torpedo FLOAT,
    pre_earnings_recommendation TEXT,
    pre_earnings_report_date TIMESTAMP,
    actual_eps FLOAT,
    actual_eps_consensus FLOAT,
    actual_surprise_percent FLOAT,
    actual_revenue FLOAT,
    actual_revenue_consensus FLOAT,
    stock_price_pre FLOAT,
    stock_reaction_1d_percent FLOAT,
    stock_reaction_5d_percent FLOAT,
    prediction_correct BOOLEAN,
    score_accuracy TEXT,
    review_text TEXT,
    lessons_learned TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ticker, quarter)
);

-- Aggregiertes Performance-Tracking
CREATE TABLE IF NOT EXISTS performance_tracking (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    period TEXT NOT NULL,
    total_predictions INT DEFAULT 0,
    correct_predictions INT DEFAULT 0,
    partially_correct INT DEFAULT 0,
    wrong_predictions INT DEFAULT 0,
    accuracy_percent FLOAT,
    avg_opportunity_score_accuracy FLOAT,
    avg_torpedo_score_accuracy FLOAT,
    best_call TEXT,
    worst_call TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(period)
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
