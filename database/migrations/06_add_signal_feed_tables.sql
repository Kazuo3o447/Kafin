-- Migration: Hinzufügen der fehlenden Tabellen signal_feed_config und trade_journal

-- Tabelle für Signal Feed Konfiguration
CREATE TABLE IF NOT EXISTS signal_feed_config (
    key         VARCHAR(80) PRIMARY KEY,
    value       JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default-Werte für Signal Feed Konfiguration
INSERT INTO signal_feed_config (key, value) VALUES
    ('torpedo_delta_min', '{"value": 1.5, "enabled": true}'),
    ('material_event', '{"value": 1, "enabled": true}'),
    ('earnings_urgent_days', '{"value": 5, "enabled": true}'),
    ('sma50_break_downtrend', '{"value": 1, "enabled": true}'),
    ('narrative_shift', '{"value": 1, "enabled": true}'),
    ('sentiment_break', '{"value": 0.1, "enabled": true}'),
    ('rvol_min', '{"value": 2.0, "enabled": true}'),
    ('earnings_warning_days', '{"value": 14, "enabled": true}'),
    ('opp_delta_min', '{"value": 1.5, "enabled": true}'),
    ('rsi_oversold', '{"value": 30.0, "enabled": true}'),
    ('rsi_overbought', '{"value": 70.0, "enabled": true}'),
    ('feed_max_signals', '{"value": 10, "enabled": true}'),
    ('dedup_hours', '{"value": 24, "enabled": true}'),
    ('quiet_period_pre_earnings_days', '{"value": 2, "enabled": true}')
ON CONFLICT (key) DO NOTHING;

-- Tabelle für Trade Journal
CREATE TABLE IF NOT EXISTS trade_journal (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    entry_date DATE NOT NULL,
    entry_price DECIMAL(10, 2),
    shares INTEGER,
    stop_price DECIMAL(10, 2),
    target_price DECIMAL(10, 2),
    thesis TEXT,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'closed', 'cancelled')),
    exit_date DATE,
    exit_price DECIMAL(10, 2),
    pnl DECIMAL(10, 2),
    pnl_percent DECIMAL(10, 2),
    alpaca_order_id TEXT,
    signal_type TEXT,
    opportunity_score DECIMAL(5, 2),
    torpedo_score DECIMAL(5, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indizes für bessere Performance
CREATE INDEX IF NOT EXISTS idx_trade_journal_ticker ON trade_journal(ticker);
CREATE INDEX IF NOT EXISTS idx_trade_journal_entry_date ON trade_journal(entry_date);
CREATE INDEX IF NOT EXISTS idx_trade_journal_status ON trade_journal(status);