"""
short_term — Kurzzeit-Gedächtnis für News-Stichpunkte

Input:  Ticker, Datum, Stichpunkte, Sentiment
Output: CRUD-Operationen auf Supabase-Tabelle short_term_memory
Deps:   db.py, config.py
Config: Keine
API:    Supabase
"""

import json
from datetime import datetime
from typing import Optional
from backend.app.config import settings
from backend.app.db import get_supabase_client
from backend.app.logger import get_logger

logger = get_logger(__name__)

_mock_memory: list[dict] = []


async def save_bullet_points(
    ticker: str,
    date: datetime,
    source: str,
    bullet_points: list[str],
    sentiment_score: float,
    category: str = "general",
    url: str = "",
    is_material: bool = False
) -> bool:
    """Speichert News-Stichpunkte im Kurzzeit-Gedächtnis."""
    quarter = f"Q{(date.month - 1) // 3 + 1}_{date.year}" if isinstance(date, datetime) else "Q1_2026"

    record = {
        "ticker": ticker,
        "date": date.isoformat() if isinstance(date, datetime) else str(date),
        "source": source,
        "bullet_points": bullet_points,
        "sentiment_score": sentiment_score,
        "category": category,
        "quarter": quarter,
        "is_material": is_material,
        "url": url
    }

    if settings.use_mock_data:
        _mock_memory.append(record)
        logger.debug(f"Mock: Stichpunkte gespeichert für {ticker}")
        return True

    try:
        db = get_supabase_client()
        if db is None:
            _mock_memory.append(record)
            return True

        record["bullet_points"] = json.dumps(bullet_points, ensure_ascii=False)
        result = db.table("short_term_memory").insert(record).execute()
        logger.debug(f"Stichpunkte gespeichert für {ticker} in Supabase")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Stichpunkte für {ticker}: {e}")
        _mock_memory.append(record)
        return False


async def get_bullet_points(ticker: str, quarter: Optional[str] = None) -> list[dict]:
    """Ruft alle Stichpunkte für einen Ticker ab."""
    if settings.use_mock_data:
        results = [m for m in _mock_memory if m["ticker"] == ticker]
        if quarter:
            results = [m for m in results if m["quarter"] == quarter]
        return sorted(results, key=lambda x: x["date"], reverse=True)

    try:
        db = get_supabase_client()
        if db is None:
            return [m for m in _mock_memory if m["ticker"] == ticker]

        query = db.table("short_term_memory").select("*").eq("ticker", ticker)
        if quarter:
            query = query.eq("quarter", quarter)
        result = query.order("date", desc=True).execute()
        return result.data
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Stichpunkte für {ticker}: {e}")
        return []


async def get_existing_urls(ticker: str) -> set[str]:
    """Gibt alle bereits gespeicherten URLs zurück (für Duplikat-Erkennung)."""
    if settings.use_mock_data:
        return {m.get("url", "") for m in _mock_memory if m["ticker"] == ticker}

    try:
        db = get_supabase_client()
        if db is None:
            return {m.get("url", "") for m in _mock_memory if m["ticker"] == ticker}
        result = db.table("short_term_memory").select("url").eq("ticker", ticker).execute()
        return {r.get("url", "") for r in result.data if r.get("url")}
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der URLs für {ticker}: {e}")
        return set()


async def get_material_news(ticker: str) -> list[dict]:
    """Ruft nur Torpedo-relevante News ab."""
    if settings.use_mock_data:
        return [m for m in _mock_memory if m["ticker"] == ticker and m.get("is_material")]

    try:
        db = get_supabase_client()
        if db is None:
            return [m for m in _mock_memory if m["ticker"] == ticker and m.get("is_material")]
        result = db.table("short_term_memory").select("*").eq("ticker", ticker).eq("is_material", True).order("date", desc=True).execute()
        return result.data
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Material-News für {ticker}: {e}")
        return []
