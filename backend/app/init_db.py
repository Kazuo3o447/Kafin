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
"""


def get_schema_extension_sql() -> str:
    """Gibt das SQL für Phase-4A-Tabellen zurück."""
    return SCHEMA_EXTENSION_SQL.strip()


def log_schema_extension_sql():
    """Loggt das benötigte SQL, damit es im Supabase Dashboard ausgeführt werden kann."""
    logger.info("Phase-4A Tabellen SQL — bitte in Supabase ausführen:")
    logger.info("\n" + get_schema_extension_sql())


async def ensure_daily_snapshots_table():
    """Erstellt die daily_snapshots Tabelle falls sie nicht existiert."""
    try:
        db = get_supabase_client()
        if db is None:
            return

        # Teste ob Tabelle existiert mit einem leeren Select
        try:
            db.table("daily_snapshots").select("id").limit(1).execute()
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
