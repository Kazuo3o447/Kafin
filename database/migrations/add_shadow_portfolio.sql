CREATE TABLE IF NOT EXISTS shadow_trades (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    quarter TEXT NOT NULL,
    audit_report_id UUID,
    signal_type TEXT NOT NULL,
    trade_direction TEXT NOT NULL,
    opportunity_score FLOAT,
    torpedo_score FLOAT,
    entry_price FLOAT,
    entry_date TIMESTAMP,
    stop_loss_price FLOAT,
    position_size_usd FLOAT DEFAULT 10000,
    exit_price FLOAT,
    exit_date TIMESTAMP,
    exit_reason TEXT,
    pnl_usd FLOAT,
    pnl_percent FLOAT,
    prediction_correct BOOLEAN,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shadow_ticker_quarter
    ON shadow_trades(ticker, quarter);
CREATE INDEX IF NOT EXISTS idx_shadow_status
    ON shadow_trades(status);
