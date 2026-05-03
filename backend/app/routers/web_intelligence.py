from fastapi import APIRouter
import asyncio
from datetime import date, timedelta

from backend.app.logger import get_logger
from backend.app.config import settings
from backend.app.memory.watchlist import get_watchlist
from backend.app.db import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/web-intelligence", tags=["web-intelligence"])

@router.post("/batch")
async def api_web_intelligence_batch():
    """
    Nacht-Batch: Aktualisiert Web Intelligence Cache für alle
    relevanten Watchlist-Ticker (Prio 1-3).
    """
    logger.info("API Call: web-intelligence/batch")

    if not settings.tavily_api_key:
        logger.warning("Web Intelligence Batch: TAVILY_API_KEY nicht gesetzt")
        return {
            "status": "skipped",
            "reason": "TAVILY_API_KEY nicht konfiguriert",
            "processed": 0,
        }

    from backend.app.data.web_search import (
        get_web_intelligence,
        _auto_prio_from_days,
    )
    from backend.app.data.finnhub import get_earnings_calendar

    wl = await get_watchlist()
    if not wl:
        return {"status": "success", "processed": 0, "skipped": 0}

    today = date.today()
    to_date = today + timedelta(days=14)
    try:
        calendar = await get_earnings_calendar(
            today.isoformat(), to_date.isoformat()
        )
        earnings_map = {
            getattr(e, "ticker", "").upper(): getattr(e, "report_date", None)
            for e in (calendar or [])
        }
    except Exception as e:
        logger.warning(f"Earnings Calendar im Batch: {e}")
        earnings_map = {}

    processed = 0
    skipped = 0
    results = []

    active_items = []
    for item in wl:
        ticker = item.get("ticker", "").upper()
        if not ticker:
            continue

        earnings_dt = earnings_map.get(ticker)
        days_to_earnings = None
        if earnings_dt:
            try:
                if hasattr(earnings_dt, "toordinal"):
                    days_to_earnings = (earnings_dt - today).days
                else:
                    from datetime import date as _d
                    days_to_earnings = (_d.fromisoformat(str(earnings_dt)) - today).days
            except Exception:
                pass

        manual_prio = item.get("web_prio")
        auto_prio = _auto_prio_from_days(days_to_earnings)
        effective_prio = manual_prio if manual_prio is not None else auto_prio

        if effective_prio == 4:
            skipped += 1
            continue

        active_items.append((item, days_to_earnings, manual_prio, effective_prio))

    CHUNK_SIZE = 5
    for i in range(0, len(active_items), CHUNK_SIZE):
        chunk = active_items[i:i + CHUNK_SIZE]

        async def _process(args):
            item, days_to_earnings, manual_prio, effective_prio = args
            ticker = item.get("ticker", "").upper()
            try:
                company_name = item.get("company_name", ticker)
                summary = await get_web_intelligence(
                    ticker=ticker,
                    company_name=company_name,
                    days_to_earnings=days_to_earnings,
                    manual_prio=manual_prio,
                    force_refresh=True,
                )
                return {
                    "ticker": ticker,
                    "prio": effective_prio,
                    "status": "ok",
                    "snippets": len(summary.split("•")) - 1 if summary else 0,
                }
            except Exception as e:
                logger.warning(f"Batch Web Intel {ticker}: {e}")
                return {"ticker": ticker, "status": "error", "error": str(e)}

        chunk_results = await asyncio.gather(
            *[_process(args) for args in chunk],
            return_exceptions=True,
        )
        for r in chunk_results:
            if isinstance(r, Exception):
                skipped += 1
            elif r.get("status") == "ok":
                processed += 1
                results.append(r)
            else:
                skipped += 1
                results.append(r)

    logger.info(f"Web Intelligence Batch: {processed} verarbeitet, {skipped} übersprungen")
    return {
        "status": "success",
        "processed": processed,
        "skipped": skipped,
        "results": results,
    }

@router.post("/refresh/{ticker}")
async def api_web_intelligence_refresh(ticker: str):
    """Manueller Refresh für einen einzelnen Ticker."""
    logger.info(f"API Call: web-intelligence/refresh/{ticker}")

    if not settings.tavily_api_key:
        return {
            "status": "error",
            "reason": "TAVILY_API_KEY nicht konfiguriert",
        }

    from backend.app.data.web_search import get_web_intelligence

    wl = await get_watchlist()
    item = next((w for w in wl if w.get("ticker", "").upper() == ticker.upper()), None)
    manual_prio = item.get("web_prio") if item else None
    company_name = item.get("company_name", ticker) if item else ticker

    summary = await get_web_intelligence(
        ticker=ticker.upper(),
        company_name=company_name,
        manual_prio=manual_prio,
        force_refresh=True,
    )
    return {
        "status": "success",
        "ticker": ticker.upper(),
        "summary": summary,
    }

@router.post("/sentiment-check")
async def api_sentiment_divergence_check():
    """Prüft alle Watchlist-Ticker auf Sentiment-Divergenz."""
    logger.info("API Call: web-intelligence/sentiment-check")
    from backend.app.analysis.sentiment_monitor import check_sentiment_divergence
    return await check_sentiment_divergence()

@router.post("/peer-check")
async def api_peer_earnings_check():
    """Prüft ob Cross-Signal-Ticker heute/morgen reporten."""
    logger.info("API Call: peer-check")
    from backend.app.analysis.peer_monitor import check_peer_earnings_today
    return await check_peer_earnings_today()

@router.post("/peer-reaction")
async def api_peer_reaction_alert(reporter: str, move_pct: float, report_timing: str = "after_hours"):
    """Sendet Peer-Reaktions-Alert nach Earnings eines Tickers."""
    logger.info(f"API Call: peer-reaction {reporter} {move_pct:+.1f}%")
    from backend.app.analysis.peer_monitor import send_peer_reaction_alert
    return await send_peer_reaction_alert(
        reporter=reporter,
        move_pct=move_pct,
        report_timing=report_timing,
    )

@router.get("/cache/{ticker}")
async def api_web_intelligence_cache(ticker: str):
    """Gibt gecachte Web Intelligence für einen Ticker zurück."""
    try:
        db = get_supabase_client()
        if not db:
            return {"ticker": ticker, "cached": False}
        res = await (
            db.table("web_intelligence_cache")
            .select("*")
            .eq("ticker", ticker.upper())
            .execute_async()
        )
        rows = res.data if res and res.data else []
        if rows:
            return {"ticker": ticker, "cached": True, **rows[0]}
        return {"ticker": ticker, "cached": False}
    except Exception as e:
        return {"ticker": ticker, "cached": False, "error": str(e)}
