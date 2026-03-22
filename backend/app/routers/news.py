from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from typing import List, Optional
from html import escape
import asyncio
from datetime import datetime, timedelta
import datetime as _dt

from backend.app.logger import get_logger
from backend.app.cache import cache_invalidate, cache_invalidate_prefix
from backend.app.memory.watchlist import get_watchlist
from backend.app.data.google_news import (
    scan_google_news,
    get_custom_search_terms,
    add_custom_search_term,
    remove_custom_search_term,
)
from backend.app.data.news_processor import run_news_pipeline, process_news_for_ticker
from backend.app.data.macro_processor import fetch_global_macro_events
from backend.app.data.sec_edgar import scan_filings_for_watchlist
from backend.app.analysis.finbert import analyze_sentiment_batch
from backend.app.alerts.telegram import send_telegram_alert
from backend.app.memory.short_term import get_bullet_points

logger = get_logger(__name__)

router = APIRouter(tags=["news"])

# --- Google News Endpoints ---

@router.get("/api/google-news/scan")
async def api_google_news_scan():
    """Scannt Google News und kombiniert Topics, Custom Terms und Watchlist."""
    watchlist = await get_watchlist()
    wl_items = [
        {
            "ticker": item.get("ticker", ""),
            "company_name": item.get("company_name", ""),
        }
        for item in watchlist
    ]
    articles = await scan_google_news(wl_items)
    return {"status": "success", "count": len(articles), "articles": articles}


@router.get("/api/google-news/search-terms")
async def api_get_search_terms():
    """Gibt alle aktiven benutzerdefinierten Suchbegriffe zurück."""
    terms = await get_custom_search_terms()
    return {"terms": terms}


@router.post("/api/google-news/search-terms")
async def api_add_search_term(term: str = Query(..., min_length=3), category: str = Query("custom")):
    """Fügt einen neuen Suchbegriff hinzu oder reaktiviert ihn."""
    success = await add_custom_search_term(term.strip(), category.strip() or "custom")
    return {"status": "success" if success else "error"}


@router.delete("/api/google-news/search-terms")
async def api_remove_search_term(term: str = Query(..., min_length=3)):
    """Deaktiviert einen bestehenden Suchbegriff."""
    success = await remove_custom_search_term(term.strip())
    return {"status": "success" if success else "error"}

# --- News Pipeline Endpoints ---

@router.post("/api/news/scan")
async def api_news_scan():
    """Führt die News-Pipeline für alle Watchlist-Ticker aus."""
    logger.info("API Call: news-scan (manuell)")
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    results = await run_news_pipeline(tickers)
    cache_invalidate("watchlist:enriched:v2")
    cache_invalidate_prefix("research_dashboard_")
    cache_invalidate_prefix("earnings_radar_")
    return {"status": "success", "results": results}

@router.post("/api/news/scan/{ticker}")
async def api_news_scan_ticker(ticker: str):
    """Führt die News-Pipeline für einen einzelnen Ticker aus."""
    logger.info(f"API Call: news-scan for {ticker}")
    result = await process_news_for_ticker(ticker)
    cache_invalidate("watchlist:enriched:v2")
    cache_invalidate(f"research_dashboard_{ticker.upper()}")
    cache_invalidate_prefix("earnings_radar_")
    return {"status": "success", "result": result}

@router.get("/api/news/memory/{ticker}")
async def api_news_memory(ticker: str):
    """Gibt alle gespeicherten Stichpunkte für einen Ticker zurück."""
    bullets = await get_bullet_points(ticker)
    return {"ticker": ticker, "count": len(bullets), "bullet_points": bullets}

@router.post("/api/news/sec-scan")
async def api_sec_scan():
    """Scannt SEC EDGAR für alle Watchlist-Ticker."""
    logger.info("API Call: sec-scan")
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    filings = await scan_filings_for_watchlist(tickers)
    return {"status": "success", "filings_found": len(filings), "filings": filings}

@router.post("/api/news/macro-scan")
async def api_macro_calendar_scan():
    """Scannt den Finnhub Wirtschaftskalender und speichert High-Impact Events unter GENERAL_MACRO."""
    logger.info("API Call: macro-calendar-scan")
    stats = await fetch_global_macro_events()
    return {"status": "success", "stats": stats}


@router.post("/api/news/scan-weekend")
async def api_news_scan_weekend():
    """Wochenend-Scan: Nur Google News + Sentiment-Alerts, kein voller Ticker-Scan."""
    logger.info("API Call: news-scan-weekend")

    wl = await get_watchlist()
    wl_items = [
        {
            "ticker": item.get("ticker", ""),
            "company_name": item.get("company_name", ""),
        }
        for item in wl
    ]

    google_news = await scan_google_news(wl_items)
    macro_events_saved = 0
    try:
        macro_stats = await fetch_global_macro_events()
        macro_events_saved = macro_stats.get("events_saved", 0)
    except Exception as exc:
        logger.debug(f"Weekend Macro Fetch Fehler: {exc}")
    alerts_sent = 0

    if google_news:
        headlines = [n["headline"] for n in google_news]
        scores = analyze_sentiment_batch(headlines)
        for item, score in zip(google_news, scores):
            if abs(score) > 0.4:
                direction = "📈" if score > 0 else "📉"
                ticker_tag = f" [{item.get('related_ticker')}]" if item.get("related_ticker") else ""
                url = item.get("url", "")
                link_line = f'\n🔗 <a href="{url}">Artikel lesen</a>' if url else ""
                headline = escape(item["headline"])
                source = escape(item.get("source", "unbekannt"))
                alert_text = (
                    f"{direction} Weekend News{ticker_tag}: {headline}\n"
                    f"Quelle: {source} | Sentiment: {score:.2f}"
                    f"{link_line}"
                )
                try:
                    await send_telegram_alert(alert_text)
                    alerts_sent += 1
                except Exception as exc:  # pragma: no cover
                    logger.debug(f"Telegram Weekend Alert Fehler: {exc}")

    count = len(google_news) if google_news else 0
    logger.info(
        f"Weekend News-Scan abgeschlossen: {count} Artikel, {alerts_sent} Alerts gesendet, Macro Events {macro_events_saved}"
    )
    return {
        "status": "success",
        "google_news_count": count,
        "alerts_sent": alerts_sent,
        "macro_events_saved": macro_events_saved,
    }
