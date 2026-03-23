"""
init_db — Datenbank-Initialisierung und Schema-Checks

Input:  Keine
Output: Keine (Logging)
Deps:   db.py, logger.py
Config: Keine
API:    Supabase (via db.py)
"""
from backend.app.db import get_supabase_client
from backend.app.logger import get_logger

logger = get_logger(__name__)

SCHEMA_EXTENSION_SQL = """
-- Langzeit-Gedächtnis: Persistente Erkenntnisse über Ticker
CREATE TABLE IF NOT EXISTS long_term_memory (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    category TEXT NOT NULL,  -- 'earnings_pattern', 'management_trust', 'guidance_reliability', 'sector_narrative', 'torpedo_history'
    insight TEXT NOT NULL,
    confidence FLOAT DEFAULT 0.5,  -- 0.0 bis 1.0
    source TEXT,  -- 'post_earnings_review', 'manual', 'news_pattern'
    quarter TEXT,  -- z.B. 'Q1_2026'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Post-Earnings Reviews: Vergleich Empfehlung vs. Realität
CREATE TABLE IF NOT EXISTS earnings_reviews (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    quarter TEXT NOT NULL,
    -- Was Kafin vorhergesagt hat
    pre_earnings_score_opportunity FLOAT,
    pre_earnings_score_torpedo FLOAT,
    pre_earnings_recommendation TEXT,  -- 'strong_buy', 'hold', 'strong_short' etc.
    pre_earnings_report_date TIMESTAMP,
    -- Was tatsächlich passiert ist
    actual_eps FLOAT,
    actual_eps_consensus FLOAT,
    actual_surprise_percent FLOAT,
    actual_revenue FLOAT,
    actual_revenue_consensus FLOAT,
    -- Kursreaktion
    stock_price_pre FLOAT,
    stock_reaction_1d_percent FLOAT,
    stock_reaction_5d_percent FLOAT,
    -- Bewertung
    prediction_correct BOOLEAN,  -- Hat die Richtung gestimmt?
    score_accuracy TEXT,  -- 'correct', 'partially_correct', 'wrong'
    review_text TEXT,  -- KI-generierte Analyse des Ergebnisses
    lessons_learned TEXT,  -- Was hat Kafin daraus gelernt?
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ticker, quarter)
);

-- Performance-Tracking: Aggregierte Trefferquote
CREATE TABLE IF NOT EXISTS performance_tracking (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    period TEXT NOT NULL,  -- 'Q1_2026', 'monthly_2026_03', 'weekly_2026_11'
    total_predictions INT DEFAULT 0,
    correct_predictions INT DEFAULT 0,
    partially_correct INT DEFAULT 0,
    wrong_predictions INT DEFAULT 0,
    accuracy_percent FLOAT,
    avg_opportunity_score_accuracy FLOAT,
    avg_torpedo_score_accuracy FLOAT,
    best_call TEXT,  -- Beste Empfehlung des Zeitraums
    worst_call TEXT,  -- Schlechteste Empfehlung
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(period)
);

-- Score-History: Zeitreihe der Opportunity- und Torpedo-Scores
CREATE TABLE IF NOT EXISTS score_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    opportunity_score FLOAT,
    torpedo_score FLOAT,
    price FLOAT,
    rsi FLOAT,
    trend TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ticker, date)
);

-- Trade Journal: Echte Positionen mit strukturierten Feldern
CREATE TABLE IF NOT EXISTS trade_journal (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(20)   NOT NULL,
    direction       VARCHAR(10)   NOT NULL DEFAULT 'long',  -- 'long' | 'short'
    entry_date      DATE          NOT NULL,
    entry_price     NUMERIC(12,4) NOT NULL,
    shares          NUMERIC(12,4),
    stop_price      NUMERIC(12,4),
    target_price    NUMERIC(12,4),
    thesis          TEXT,
    opportunity_score NUMERIC(4,1),
    torpedo_score     NUMERIC(4,1),
    recommendation  VARCHAR(50),
    exit_date       DATE,
    exit_price      NUMERIC(12,4),
    exit_reason     VARCHAR(100),  -- 'stop_hit' | 'target_hit' | 'manual' | 'earnings_reaction'
    notes           TEXT,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_ticker
ON trade_journal(ticker);

CREATE INDEX IF NOT EXISTS idx_journal_entry_date
ON trade_journal(entry_date DESC);

CREATE TABLE IF NOT EXISTS signal_feed_config (
    key         VARCHAR(80) PRIMARY KEY,
    value       JSONB       NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


CUSTOM_SEARCH_TERMS_SQL = """
CREATE TABLE IF NOT EXISTS custom_search_terms (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    term TEXT NOT NULL UNIQUE,
    category TEXT DEFAULT 'custom',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO custom_search_terms (term, category) VALUES
    ('Federal Reserve interest rates', 'macro'),
    ('US tariffs trade war', 'geopolitik'),
    ('sanctions geopolitical', 'geopolitik'),
    ('oil OPEC production', 'commodities'),
    ('inflation CPI consumer prices', 'macro'),
    ('jobs NFP unemployment', 'macro'),
    ('earnings season results', 'earnings'),
    ('recession economic slowdown', 'macro'),
    ('US China relations', 'geopolitik'),
    ('semiconductor chip shortage', 'sector')
ON CONFLICT (term) DO NOTHING;
"""


def get_schema_extension_sql() -> str:
    """Gibt das SQL für Phase-4A-Tabellen zurück."""
    return SCHEMA_EXTENSION_SQL.strip()


def log_schema_extension_sql():
    """Loggt das benötigte SQL, damit es im Supabase Dashboard ausgeführt werden kann."""
    logger.info("Phase-4A Tabellen SQL — bitte in Supabase ausführen:")
    logger.info("\n" + get_schema_extension_sql())
    logger.info("\nScore History SQL (für delta tracking):\n"
                "CREATE TABLE IF NOT EXISTS score_history (\n"
                "    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,\n"
                "    ticker TEXT NOT NULL,\n"
                "    date DATE NOT NULL,\n"
                "    opportunity_score FLOAT,\n"
                "    torpedo_score FLOAT,\n"
                "    price FLOAT,\n"
                "    rsi FLOAT,\n"
                "    trend TEXT,\n"
                "    created_at TIMESTAMP DEFAULT NOW(),\n"
                "    UNIQUE(ticker, date)\n"
                ");")


def get_custom_search_terms_sql() -> str:
    """Gibt das SQL für benutzerdefinierte News-Suchbegriffe zurück."""
    return CUSTOM_SEARCH_TERMS_SQL.strip()


def log_custom_search_terms_sql():
    """Loggt das SQL für die custom_search_terms-Tabelle zur manuellen Ausführung."""
    logger.info("Custom Search Terms SQL — bitte in Supabase ausführen:")
    logger.info("\n" + get_custom_search_terms_sql())
    logger.info("\nNarrative Shift Migration SQL — bitte in Supabase ausführen:")
    logger.info("""
ALTER TABLE short_term_memory 
ADD COLUMN IF NOT EXISTS url TEXT,
ADD COLUMN IF NOT EXISTS is_narrative_shift BOOLEAN DEFAULT false,
ADD COLUMN IF NOT EXISTS shift_type TEXT,
ADD COLUMN IF NOT EXISTS shift_confidence FLOAT,
ADD COLUMN IF NOT EXISTS shift_reasoning TEXT;

CREATE INDEX IF NOT EXISTS idx_stm_narrative_shift ON short_term_memory(ticker, is_narrative_shift) WHERE is_narrative_shift = true;
    """)


async def ensure_daily_snapshots_table():
    """Erstellt die daily_snapshots Tabelle falls sie nicht existiert."""
    try:
        db = get_supabase_client()
        if db is None:
            return

        # Teste ob Tabelle existiert mit einem leeren Select
        try:
            await db.table("daily_snapshots").select("id").limit(1).execute_async()
            logger.info("Tabelle daily_snapshots existiert bereits.")
        except Exception:
            logger.warning("Tabelle daily_snapshots fehlt. Bitte manuell in Supabase anlegen:")
            logger.warning("""
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
            """)
    except Exception as e:
        logger.error(f"daily_snapshots Check fehlgeschlagen: {e}")


async def ensure_signal_feed_config():
    """Erstellt signal_feed_config Tabelle und fügt Defaults ein."""
    try:
        db = get_supabase_client()
        if db is None:
            return

        # Tabelle erstellen (wenn nicht vorhanden)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signal_feed_config (
                key         VARCHAR(80) PRIMARY KEY,
                value       JSONB       NOT NULL,
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

        # Default-Werte einfügen (ON CONFLICT = nicht überschreiben wenn User geändert hat)
        import json
        defaults = [
            ("torpedo_delta_min",       {"value": 1.5,  "enabled": True}),
            ("material_event",          {"value": 1,    "enabled": True}),
            ("earnings_urgent_days",    {"value": 5,    "enabled": True}),
            ("sma50_break_downtrend",   {"value": 1,    "enabled": True}),
            ("narrative_shift",         {"value": 1,    "enabled": True}),
            ("sentiment_break",         {"value": 0.1,  "enabled": True}),
            ("rvol_min",                {"value": 2.0,  "enabled": True}),
            ("earnings_warning_days",   {"value": 14,   "enabled": True}),
            ("opp_delta_min",           {"value": 1.5,  "enabled": True}),
            ("rsi_oversold",            {"value": 30.0, "enabled": True}),
            ("rsi_overbought",          {"value": 70.0, "enabled": True}),
            ("feed_max_signals",        {"value": 10,   "enabled": True}),
            ("dedup_hours",             {"value": 24,   "enabled": True}),
            ("quiet_period_pre_earnings_days", {"value": 2, "enabled": True}),
        ]
        for key, val in defaults:
            await db.execute("""
                INSERT INTO signal_feed_config (key, value)
                VALUES ($1, $2)
                ON CONFLICT (key) DO NOTHING
            """, key, json.dumps(val))
        
        logger.info("signal_feed_config Tabelle erstellt und Defaults eingefügt")
    except Exception as e:
        logger.error(f"signal_feed_config Setup fehlgeschlagen: {e}")


async def add_after_market_summary_column():
    """Fügt after_market_summary Spalte zu daily_snapshots hinzu falls nicht vorhanden."""
    try:
        db = get_supabase_client()
        if db is None:
            return

        # After-Market Spalte zu daily_snapshots (falls noch nicht vorhanden)
        await db.execute("""
            ALTER TABLE daily_snapshots
            ADD COLUMN IF NOT EXISTS after_market_summary TEXT;
        """)
        
        logger.info("after_market_summary Spalte zu daily_snapshots hinzugefügt (falls nicht vorhanden)")
    except Exception as e:
        logger.error(f"After-Market Summary Spalte hinzufügen fehlgeschlagen: {e}")


async def init_db():
    """Initialisiert die Datenbank mit allen Tabellen und Defaults."""
    await ensure_daily_snapshots_table()
    await ensure_signal_feed_config()
    await add_after_market_summary_column()
