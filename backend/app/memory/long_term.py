"""
long_term — Persistentes Langzeit-Gedächtnis für Ticker-Erkenntnisse

Input:  Ticker, Kategorie, Erkenntnis
Output: CRUD auf Supabase-Tabelle long_term_memory
Deps:   db.py, config.py
Config: Keine
API:    Supabase
"""

from datetime import datetime
from typing import Optional
from backend.app.db import get_supabase_client
from backend.app.utils.timezone import now_mez
from backend.app.logger import get_logger

logger = get_logger(__name__)


async def save_insight(
    ticker: str,
    category: str,
    insight: str,
    confidence: float = 0.5,
    source: str = "post_earnings_review",
    quarter: Optional[str] = None,
) -> bool:
    """Speichert eine Erkenntnis im Langzeit-Gedächtnis."""
    if quarter is None:
        now = now_mez()
        quarter = f"Q{(now.month - 1) // 3 + 1}_{now.year}"

    record = {
        "ticker": ticker,
        "category": category,
        "insight": insight,
        "confidence": confidence,
        "source": source,
        "quarter": quarter,
        "updated_at": now_mez().isoformat(),
    }

    try:
        db = get_supabase_client()
        if db is None:
            logger.warning("Supabase nicht verfügbar. Insight nicht gespeichert.")
            return False

        await db.table("long_term_memory").insert(record).execute_async()
        logger.info(f"Langzeit-Insight gespeichert: [{ticker}] {category}: {insight[:60]}...")
        return True
    except Exception as e:
        logger.error(f"Langzeit-Speicher Fehler: {e}")
        return False


async def get_insights(ticker: str, category: Optional[str] = None) -> list[dict]:
    """Ruft alle Erkenntnisse für einen Ticker ab."""
    try:
        db = get_supabase_client()
        if db is None:
            return []

        query = db.table("long_term_memory").select("*").eq("ticker", ticker)
        if category:
            query = query.eq("category", category)
        result = await query.order("updated_at", desc=True).execute_async()
        return result.data
    except Exception as e:
        logger.error(f"Langzeit-Abruf Fehler für {ticker}: {e}")
        return []


async def get_all_insights_for_report(ticker: str) -> str:
    """Formatiert Erkenntnisse für Audit-Report-Prompts."""
    insights = await get_insights(ticker)
    if not insights:
        return "Keine historischen Erkenntnisse vorhanden (erster Report für diesen Ticker)."

    lines = []
    for entry in insights[:10]:
        conf = entry.get("confidence", 0)
        conf_str = "hoch" if conf > 0.7 else "mittel" if conf > 0.4 else "niedrig"
        category = entry.get("category", "?")
        insight = entry.get("insight", "")
        lines.append(f"[{category}] (Konfidenz: {conf_str}) {insight}")

    return "\n".join(lines)
