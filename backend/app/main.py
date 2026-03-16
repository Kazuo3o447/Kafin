"""
main — FastAPI Entrypoint

Input:  HTTP Requests (REST)
Output: HTTP Responses (JSON)
Deps:   FastAPI, config, logger, schemas, admin
Config: app_name, environment
API:    Keine externen (nur intern)
"""
from fastapi import FastAPI
from backend.app.config import settings
from backend.app.logger import get_logger
from backend.app.admin import router as admin_router
from backend.app.init_watchlist import ensure_watchlist_populated
from schemas.base import HealthCheckResponse

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API für die Kafin Earnings-Trading-Plattform",
)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starter {settings.app_name} im [{settings.environment}] Modus.")
    logger.info("Admin Panel is available at /admin")
    if settings.use_mock_data:
        logger.warning("Mock-Data-Modus ist AKTIV. Es werden keine echten APIs aufgerufen.")
    await ensure_watchlist_populated()

app.include_router(admin_router)

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Prüft, ob die API erreichbar ist."""
    return HealthCheckResponse(status="ok", version="1.0.0")

from backend.app.analysis.finbert import analyze_sentiment

@app.post("/api/finbert/analyze")
async def api_finbert_analyze(text: str):
    score = analyze_sentiment(text)
    return {"text": text, "sentiment_score": score}

from fastapi import APIRouter
from typing import List

from backend.app.data.finnhub import (
    get_earnings_calendar, get_company_news, get_short_interest, get_insider_transactions
)
from backend.app.data.fmp import (
    get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics
)
from backend.app.data.fred import get_macro_snapshot

from schemas.earnings import EarningsExpectation, EarningsHistorySummary
from schemas.sentiment import NewsBulletPoint, ShortInterestData, InsiderActivity
from schemas.valuation import ValuationData
from schemas.macro import MacroSnapshot

data_router = APIRouter(prefix="/api/data", tags=["data"])

@data_router.get("/earnings-calendar", response_model=List[EarningsExpectation])
async def api_earnings_calendar(from_date: str, to_date: str):
    logger.info(f"API Call: earnings-calendar {from_date} to {to_date}")
    return await get_earnings_calendar(from_date, to_date)

@data_router.get("/company/{ticker}/news", response_model=List[NewsBulletPoint])
async def api_company_news(ticker: str, from_date: str = "2026-01-01", to_date: str = "2026-12-31"):
    logger.info(f"API Call: company-news for {ticker}")
    return await get_company_news(ticker, from_date, to_date)

@data_router.get("/company/{ticker}/short-interest", response_model=ShortInterestData)
async def api_short_interest(ticker: str):
    logger.info(f"API Call: short-interest for {ticker}")
    return await get_short_interest(ticker)

@data_router.get("/company/{ticker}/insiders", response_model=InsiderActivity)
async def api_insiders(ticker: str):
    logger.info(f"API Call: insiders for {ticker}")
    return await get_insider_transactions(ticker)

@data_router.get("/company/{ticker}/profile", response_model=ValuationData)
async def api_profile(ticker: str):
    logger.info(f"API Call: profile for {ticker}")
    return await get_company_profile(ticker)

@data_router.get("/company/{ticker}/estimates", response_model=EarningsExpectation)
async def api_estimates(ticker: str):
    logger.info(f"API Call: estimates for {ticker}")
    return await get_analyst_estimates(ticker)

@data_router.get("/company/{ticker}/earnings-history", response_model=EarningsHistorySummary)
async def api_earnings_history(ticker: str):
    logger.info(f"API Call: earnings-history for {ticker}")
    return await get_earnings_history(ticker)

@data_router.get("/macro", response_model=MacroSnapshot)
async def api_macro():
    logger.info(f"API Call: macro snapshot")
    return await get_macro_snapshot()

from backend.app.memory.watchlist import (
    get_watchlist, add_ticker, remove_ticker, update_ticker, get_earnings_this_week
)
from pydantic import BaseModel
from typing import Optional, List

# Watchlist Router
watchlist_router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

class WatchlistItemCreate(BaseModel):
    ticker: str
    company_name: str
    sector: str
    notes: Optional[str] = ""
    cross_signals: Optional[List[str]] = []

class WatchlistItemUpdate(BaseModel):
    company_name: Optional[str] = None
    sector: Optional[str] = None
    notes: Optional[str] = None
    cross_signals: Optional[List[str]] = None

@watchlist_router.get("")
async def api_get_watchlist():
    logger.info("API Call: get-watchlist")
    return await get_watchlist()

@watchlist_router.post("")
async def api_add_watchlist_item(item: WatchlistItemCreate):
    logger.info(f"API Call: add-watchlist-item {item.ticker}")
    return await add_ticker(
        item.ticker, item.company_name, item.sector, item.notes, item.cross_signals
    )

@watchlist_router.get("/earnings-this-week")
async def api_watchlist_earnings_this_week():
    logger.info("API Call: watchlist-earnings-this-week")
    from datetime import datetime, timedelta
    now = datetime.now()
    end_of_week = now + timedelta(days=7)
    from_date = now.strftime("%Y-%m-%d")
    to_date = end_of_week.strftime("%Y-%m-%d")
    
    cal = await get_earnings_calendar(from_date, to_date)
    wl = await get_watchlist()
    return await get_earnings_this_week(wl, cal)

@watchlist_router.put("/{ticker}")
async def api_update_watchlist_item(ticker: str, item: WatchlistItemUpdate):
    logger.info(f"API Call: update-watchlist-item {ticker}")
    update_data = {k: v for k, v in item.dict().items() if v is not None}
    return await update_ticker(ticker, **update_data)

@watchlist_router.delete("/{ticker}")
async def api_remove_watchlist_item(ticker: str):
    logger.info(f"API Call: remove-watchlist-item {ticker}")
    success = await remove_ticker(ticker)
    if success:
         return {"status": "success"}
    return {"status": "error"}

from backend.app.data.news_processor import run_news_pipeline, process_news_for_ticker
from backend.app.data.macro_processor import fetch_global_macro_events

news_router = APIRouter(prefix="/api/news", tags=["news"])

@news_router.post("/scan")
async def api_news_scan():
    """Führt die News-Pipeline für alle Watchlist-Ticker aus."""
    logger.info("API Call: news-scan (manuell)")
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    results = await run_news_pipeline(tickers)
    return {"status": "success", "results": results}

@news_router.post("/scan/{ticker}")
async def api_news_scan_ticker(ticker: str):
    """Führt die News-Pipeline für einen einzelnen Ticker aus."""
    logger.info(f"API Call: news-scan for {ticker}")
    result = await process_news_for_ticker(ticker)
    return {"status": "success", "result": result}

@news_router.get("/memory/{ticker}")
async def api_news_memory(ticker: str):
    """Gibt alle gespeicherten Stichpunkte für einen Ticker zurück."""
    from backend.app.memory.short_term import get_bullet_points
    bullets = await get_bullet_points(ticker)
    return {"ticker": ticker, "count": len(bullets), "bullet_points": bullets}

@news_router.post("/sec-scan")
async def api_sec_scan():
    """Scannt SEC EDGAR für alle Watchlist-Ticker."""
    logger.info("API Call: sec-scan")
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    filings = await scan_filings_for_watchlist(tickers)
    return {"status": "success", "filings_found": len(filings), "filings": filings}

@news_router.post("/macro-scan")
async def api_macro_calendar_scan():
    """Scannt den Finnhub Wirtschaftskalender und speichert High-Impact Events unter GENERAL_MACRO."""
    logger.info("API Call: macro-calendar-scan")
    stats = await fetch_global_macro_events()
    return {"status": "success", "stats": stats}

app.include_router(news_router)

from backend.app.n8n_setup import setup_workflows

@app.post("/api/n8n/setup")
async def api_n8n_setup():
    """Erstellt die n8n-Workflows automatisch."""
    await setup_workflows()
    return {"status": "success", "message": "n8n Workflows wurden erstellt"}

from backend.app.analysis.report_generator import generate_audit_report, generate_sunday_report, generate_morning_briefing
from backend.app.data.market_overview import get_market_overview as fetch_market_overview

# Report Router
reports_router = APIRouter(prefix="/api/reports", tags=["reports"])

# In-Memory latest report for the mocked endpoint
_latest_report = ""

@reports_router.post("/generate/{ticker}")
async def api_generate_report(ticker: str):
    """
    Generiert einen einzelnen Audit-Report für den angegebenen Ticker.
    Der Report wird über DeepSeek erstellt und im Arbeitsspeicher gespeichert.
    """
    logger.info(f"[Report] Starte Audit-Report für {ticker}...")
    global _latest_report
    try:
        report_text = await generate_audit_report(ticker)
        _latest_report = report_text
        logger.info(f"[Report] Audit-Report für {ticker} erfolgreich generiert ({len(report_text)} Zeichen).")
        return {"status": "success", "report": report_text}
    except Exception as e:
        logger.error(f"[Report] Fehler beim Generieren des Audit-Reports für {ticker}: {e}")
        return {"status": "error", "message": str(e)}

@reports_router.post("/generate-sunday")
async def api_generate_sunday_report():
    """
    Erstellt den wöchentlichen Sonntags-Report und schickt ihn via Telegram.

    HINWEIS: Der ursprüngliche E-Mail-Versand (SMTP) ist bewusst deaktiviert.
    Grund: SMTP ist in der Build-Phase nicht konfiguriert.
    Geplant: In der Endphase wird die send_sunday_report() Funktion aus alerts/email.py
             aktiviert und parallel zum Telegram-Alert genutzt.
    Aktuelle Lösung: Report wird per Telegram Bot als Textnachricht zugestellt.
    """
    logger.info("[SundayReport] Starte wöchentlichen Sonntags-Report...")
    
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    logger.info(f"[SundayReport] Watchlist geladen. {len(tickers)} Ticker: {tickers}")
    
    global _latest_report
    
    try:
        report_text = await generate_sunday_report(tickers)
        _latest_report = report_text
        logger.info(f"[SundayReport] Report generiert. Größe: {len(report_text)} Zeichen.")
    except Exception as e:
        logger.error(f"[SundayReport] Fehler beim Generieren des Reports: {e}")
        return {"status": "error", "message": str(e)}

    # ---------------------------------------------------------------
    # TELEGRAM-VERSAND (Aktiv / Primärer Versandweg in der Build-Phase)
    # ---------------------------------------------------------------
    # Da Telegram die Nachricht auf max. 4096 Zeichen begrenzt,
    # teilen wir lange Reports in Blöcke à 4000 Zeichen auf.
    try:
        from backend.app.alerts.telegram import send_telegram_alert
        
        MAX_CHUNK = 4000
        chunks = [report_text[i:i+MAX_CHUNK] for i in range(0, len(report_text), MAX_CHUNK)]
        
        logger.info(f"[SundayReport] Sende Report via Telegram ({len(chunks)} Nachrichten)...")
        for idx, chunk in enumerate(chunks):
            prefix = f"📊 <b>KAFIN SUNDAY REPORT</b> ({idx+1}/{len(chunks)})\n\n" if idx == 0 else f"<b>[Fortsetzung {idx+1}/{len(chunks)}]</b>\n\n"
            success = await send_telegram_alert(prefix + chunk)
            if not success:
                logger.warning(f"[SundayReport] Telegram-Versand Chunk {idx+1} fehlgeschlagen.")
        
        logger.info("[SundayReport] Telegram-Versand abgeschlossen.")
    except Exception as e:
        logger.error(f"[SundayReport] Telegram-Versand fehlgeschlagen: {e}")

    # ---------------------------------------------------------------
    # E-MAIL DEAKTIVIERT (Build-Phase)
    # ---------------------------------------------------------------
    # TODO (Endphase): SMTP konfigurieren und folgende Zeilen reaktivieren:
    # from backend.app.alerts.email import send_sunday_report
    # asyncio.create_task(send_sunday_report(report_text))
    # ---------------------------------------------------------------
        
    return {"status": "success", "report": report_text}

@reports_router.post("/generate-morning")
async def api_generate_morning_briefing():
    """Generiert das tägliche Morning Briefing."""
    logger.info("[MorningBriefing] Starte Morning Briefing...")
    global _latest_report
    try:
        report = await generate_morning_briefing()
        _latest_report = report
        logger.info(f"[MorningBriefing] Briefing generiert. Größe: {len(report)} Zeichen.")
    except Exception as e:
        logger.error(f"[MorningBriefing] Fehler: {e}")
        return {"status": "error", "message": str(e)}

    # Per Telegram senden
    try:
        from backend.app.alerts.telegram import send_telegram_alert

        MAX_CHUNK = 4000
        chunks = [report[i:i+MAX_CHUNK] for i in range(0, len(report), MAX_CHUNK)]
        logger.info(f"[MorningBriefing] Sende via Telegram ({len(chunks)} Nachrichten)...")
        for idx, chunk in enumerate(chunks):
            prefix = f"📊 <b>KAFIN MORNING BRIEFING</b> ({idx+1}/{len(chunks)})\n\n" if idx == 0 else f"<b>[Fortsetzung {idx+1}/{len(chunks)}]</b>\n\n"
            await send_telegram_alert(prefix + chunk)
        logger.info("[MorningBriefing] Telegram-Versand abgeschlossen.")
    except Exception as e:
        logger.error(f"[MorningBriefing] Telegram-Versand fehlgeschlagen: {e}")

    return {"status": "success", "report": report}

@reports_router.get("/latest")
async def api_get_latest_report():
    logger.info("[Report] API Call: get-latest-report")
    return {"report": _latest_report}

@data_router.get("/market-overview")
async def api_market_overview():
    """Gibt die aktuelle Marktübersicht zurück (Indizes, Sektoren, Makro)."""
    logger.info("API Call: market-overview")
    overview = await fetch_market_overview()
    return overview

app.include_router(data_router)
app.include_router(watchlist_router)
app.include_router(reports_router)

