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
    is_material: bool = False,
    is_narrative_shift: bool = False,
    shift_type: Optional[str] = None,
    shift_confidence: Optional[float] = None,
    shift_reasoning: Optional[str] = None
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
        "url": url,
        "is_narrative_shift": is_narrative_shift,
        "shift_type": shift_type,
        "shift_confidence": shift_confidence,
        "shift_reasoning": shift_reasoning
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


async def get_bullet_points_batch(
    tickers: list[str],
    limit_per_ticker: int = 10,
) -> dict[str, list[dict]]:
    """
    Lädt News-Bullets für MEHRERE Ticker in EINER DB-Query.
    Analog zu _fetch_all_scores_sync für score_history.

    Returns: {ticker_upper: [row, row, ...]} sortiert nach
    date desc, max limit_per_ticker Rows pro Ticker.
    """
    if not tickers:
        return {}

    if settings.use_mock_data:
        result = {}
        for t in tickers:
            t_up = t.upper()
            rows = [m for m in _mock_memory
                    if m["ticker"] == t_up]
            rows.sort(
                key=lambda x: x.get("date", ""),
                reverse=True
            )
            result[t_up] = rows[:limit_per_ticker]
        return result

    try:
        db = get_supabase_client()
        if db is None:
            return {}

        tickers_upper = list(dict.fromkeys(t.upper() for t in tickers if t))
        # Eine Query für alle Ticker
        res = (
            db.table("short_term_memory")
            .select(
                "ticker,date,sentiment_score,"
                "is_material,shift_type,bullet_points"
            )
            .in_("ticker", tickers_upper)
            .order("date", desc=True)
            .limit(max(limit_per_ticker * len(tickers_upper) * 2, limit_per_ticker))
            .execute()
        )
        rows = res.data if res and res.data else []

        by_ticker: dict[str, list[dict]] = {}
        for row in rows:
            t = row.get("ticker", "").upper()
            if t not in by_ticker:
                by_ticker[t] = []
            if len(by_ticker[t]) < limit_per_ticker:
                by_ticker[t].append(row)

        # Fairness-Fallback: falls ein Ticker durch die globale Limitierung
        # unterfüllt ist, laden wir ihn einmal gezielt nach.
        for ticker in tickers_upper:
            if len(by_ticker.get(ticker, [])) >= limit_per_ticker:
                continue
            try:
                full_rows = await get_bullet_points(ticker)
                if full_rows:
                    by_ticker[ticker] = full_rows[:limit_per_ticker]
            except Exception:
                continue

        return by_ticker

    except Exception as e:
        logger.error(
            f"get_bullet_points_batch error: {e}"
        )
        return {}


def _calc_sentiment_from_bullets(
    bullets: list[dict],
) -> dict:
    """
    Berechnet aggregierte Sentiment-Metriken aus Bullet-Liste.
    Wiederverwendbar überall wo Sentiment berechnet wird.

    Returns dict mit:
      avg: float — Durchschnitt aller Scores
      trend: "improving"|"deteriorating"|"stable"
      has_material: bool — is_material Event vorhanden
      count: int — Anzahl analysierter Artikel
      label: "bullish"|"bearish"|"neutral"
    """
    if not bullets:
        return {
            "avg": 0.0, "trend": "stable",
            "has_material": False, "count": 0,
            "label": "neutral",
        }

    scores = []
    for b in bullets:
        raw = b.get("sentiment_score")
        if raw is not None:
            try:
                scores.append(float(raw))
            except (ValueError, TypeError):
                pass

    if not scores:
        return {
            "avg": 0.0, "trend": "stable",
            "has_material": any(
                b.get("is_material") for b in bullets
            ),
            "count": 0, "label": "neutral",
        }

    avg = round(sum(scores) / len(scores), 3)

    # Trend: Vergleich der letzten 3 vs älteren
    if len(scores) >= 4:
        recent = sum(scores[:3]) / 3
        older  = sum(scores[3:]) / len(scores[3:])
        if recent < older - 0.15:
            trend = "deteriorating"
        elif recent > older + 0.15:
            trend = "improving"
        else:
            trend = "stable"
    else:
        trend = "stable"

    label = (
        "bullish"  if avg >  0.15 else
        "bearish"  if avg < -0.15 else
        "neutral"
    )

    return {
        "avg":          avg,
        "trend":        trend,
        "has_material": any(
            b.get("is_material") for b in bullets
        ),
        "count":        len(scores),
        "label":        label,
    }


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
