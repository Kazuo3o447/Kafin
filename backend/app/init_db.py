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
