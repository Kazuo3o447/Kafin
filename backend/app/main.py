"""
main — FastAPI Entrypoint

Input:  HTTP Requests (REST)
Output: HTTP Responses (JSON)
Deps:   FastAPI, config, logger, schemas, admin
Config: app_name, environment
API:    Keine externen (nur intern)
"""
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.logger import get_logger, get_recent_logs
from backend.app.admin import router as admin_router
from backend.app.init_watchlist import ensure_watchlist_populated
from backend.app.init_db import (
    ensure_daily_snapshots_table,
    log_schema_extension_sql,
    get_schema_extension_sql,
)
from backend.app.analysis.post_earnings_review import run_post_earnings_review
from backend.app.memory.long_term import get_insights
from backend.app.db import get_supabase_client
from schemas.base import HealthCheckResponse

logger = get_logger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API für die Kafin Earnings-Trading-Plattform",
)

# CORS Middleware für Frontend-Zugriff
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starter {settings.app_name} im [{settings.environment}] Modus.")
    logger.info("Admin Panel ist verfügbar bei /admin")
    if settings.use_mock_data:
        logger.warning("Mock-Data-Modus ist AKTIV. Es werden keine echten APIs aufgerufen.")
    await ensure_watchlist_populated()
    await ensure_daily_snapshots_table()
    log_schema_extension_sql()

app.include_router(admin_router)

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Prüft, ob die API erreichbar ist."""
    return HealthCheckResponse(status="ok", version="1.0.0")


@app.post("/api/admin/init-tables")
async def api_admin_init_tables():
    """Gibt das SQL für Phase-4A Tabellen zurück."""
    sql = get_schema_extension_sql()
    logger.info("API Call: admin init tables SQL ausgegeben")
    return {"status": "success", "sql": sql}

@app.get("/api/logs")
async def api_get_logs(level: str = None, limit: int = 100):
    """Gibt die letzten Log-Einträge zurück."""
    logs = get_recent_logs()
    if level:
        logs = [l for l in logs if l.get("level") == level]
    return {"logs": logs[:limit]}

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
from backend.app.data.yfinance_data import (
    get_risk_metrics, get_atm_implied_volatility, get_historical_volatility
)
from backend.app.analysis.scoring import calculate_quality_score, calculate_mismatch_score

from schemas.earnings import EarningsExpectation, EarningsHistorySummary
from schemas.sentiment import NewsBulletPoint, ShortInterestData, InsiderActivity
from schemas.valuation import ValuationData
from schemas.macro import MacroSnapshot
from schemas.options import OptionsData

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


@data_router.get("/long-term-memory/{ticker}")
async def api_long_term_memory(ticker: str):
    """Gibt das Langzeit-Gedächtnis für einen Ticker zurück."""
    insights = await get_insights(ticker)
    return {"ticker": ticker, "count": len(insights), "insights": insights}


@data_router.get("/performance")
async def api_performance():
    """Aggregierte Trefferquote aus Supabase."""
    try:
        db = get_supabase_client()
        if db:
            result = db.table("performance_tracking").select("*").order("period", desc=True).execute()
            return {"status": "success", "performance": result.data}
        return {"status": "error", "message": "Supabase nicht verbunden"}
    except Exception as e:
        logger.error(f"Performance-Endpoint Fehler: {e}")
        return {"status": "error", "message": str(e)}


@data_router.get("/options/{ticker}", response_model=OptionsData)
async def api_options_data(ticker: str):
    """Holt Options-Daten inkl. IV ATM, Put/Call Ratio, historischer Volatilität."""
    logger.info(f"API Call: options-data for {ticker}")
    options_data = await get_atm_implied_volatility(ticker)
    if options_data is None:
        return OptionsData(ticker=ticker)
    return options_data


@data_router.get("/risk-metrics/{ticker}")
async def api_risk_metrics(ticker: str):
    """Holt Risk-Metriken: Beta, historische Volatilität."""
    logger.info(f"API Call: risk-metrics for {ticker}")
    
    # Beta
    risk_data = await get_risk_metrics(ticker)
    beta = risk_data.get("beta")
    
    # Historische Volatilität (20 und 60 Tage)
    hist_vol_20d = await get_historical_volatility(ticker, days=20)
    hist_vol_60d = await get_historical_volatility(ticker, days=60)
    
    return {
        "ticker": ticker,
        "beta": beta,
        "historical_volatility_20d": hist_vol_20d,
        "historical_volatility_60d": hist_vol_60d
    }


@data_router.get("/contrarian-opportunities")
async def api_contrarian_opportunities(min_mismatch_score: float = 50.0):
    """
    Findet Contrarian-Trading-Opportunities in der Watchlist.
    
    Kriterien:
    - Sentiment < -0.5 (extrem negativ)
    - Quality Score > 6/10 (Fundamentals intakt)
    - Beta > 1.2 (volatile Aktie)
    - Mismatch Score > min_mismatch_score
    """
    logger.info(f"API Call: contrarian-opportunities (min_mismatch_score={min_mismatch_score})")
    
    try:
        from backend.app.memory.watchlist import get_watchlist
        
        watchlist = await get_watchlist()
        opportunities = []
        
        for item in watchlist:
            ticker = item.get("ticker")
            
            try:
                # 1. Sentiment (letzte 7 Tage)
                news_memory = await get_memory_for_ticker(ticker)
                if not news_memory:
                    continue
                
                # Durchschnittlicher Sentiment der letzten 7 Tage
                recent_bullets = news_memory[:7]  # Annahme: chronologisch sortiert
                if not recent_bullets:
                    continue
                
                sentiment_scores = [b.get("sentiment_score", 0) for b in recent_bullets if b.get("sentiment_score") is not None]
                if not sentiment_scores:
                    continue
                
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                
                # Filter: Sentiment muss extrem negativ sein
                if avg_sentiment >= -0.5:
                    continue
                
                # 2. Beta
                risk_data = await get_risk_metrics(ticker)
                beta = risk_data.get("beta")
                if beta is None or beta < 1.2:
                    continue
                
                # 3. Quality Score
                key_metrics = await get_key_metrics(ticker)
                if not key_metrics:
                    continue
                
                quality_score = calculate_quality_score(
                    debt_to_equity=key_metrics.debt_to_equity,
                    current_ratio=key_metrics.current_ratio,
                    free_cash_flow_yield=key_metrics.free_cash_flow_yield,
                    pe_ratio=key_metrics.pe_ratio
                )
                
                # Filter: Quality muss gut sein
                if quality_score < 6.0:
                    continue
                
                # 4. Options-Daten
                options_data = await get_atm_implied_volatility(ticker)
                iv_atm = options_data.implied_volatility_atm if options_data else None
                hist_vol = options_data.historical_volatility if options_data else None
                
                # 5. Mismatch Score berechnen
                mismatch_score = calculate_mismatch_score(
                    sentiment_score=avg_sentiment,
                    quality_score=quality_score,
                    beta=beta,
                    iv_atm=iv_atm,
                    hist_vol=hist_vol
                )
                
                # Filter: Mismatch Score muss hoch genug sein
                if mismatch_score < min_mismatch_score:
                    continue
                
                # Material News Count
                material_count = sum(1 for b in recent_bullets if b.get("is_material", False))
                
                opportunities.append({
                    "ticker": ticker,
                    "mismatch_score": mismatch_score,
                    "sentiment_7d": round(avg_sentiment, 3),
                    "quality_score": quality_score,
                    "beta": beta,
                    "iv_atm": iv_atm,
                    "hist_vol": hist_vol,
                    "iv_spread": round(iv_atm - hist_vol, 2) if (iv_atm and hist_vol) else None,
                    "material_news_count": material_count,
                    "debt_to_equity": key_metrics.debt_to_equity,
                    "current_ratio": key_metrics.current_ratio,
                    "fcf_yield": key_metrics.free_cash_flow_yield
                })
                
            except Exception as e:
                logger.debug(f"Contrarian-Check für {ticker} fehlgeschlagen: {e}")
                continue
        
        # Sortiere nach Mismatch Score (höchste zuerst)
        opportunities.sort(key=lambda x: x["mismatch_score"], reverse=True)
        
        logger.info(f"Gefunden: {len(opportunities)} Contrarian-Opportunities")
        return {
            "status": "success",
            "count": len(opportunities),
            "opportunities": opportunities
        }
        
    except Exception as e:
        logger.error(f"Contrarian-Opportunities Fehler: {e}")
        return {"status": "error", "message": str(e), "opportunities": []}

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
from backend.app.data.sec_edgar import scan_filings_for_watchlist

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


@reports_router.post("/post-earnings-review/{ticker}")
async def api_post_earnings_review(ticker: str, quarter: str | None = None):
    """Führt einen Post-Earnings-Review für einen Ticker durch."""
    logger.info(f"API Call: post-earnings-review for {ticker}")
    review = await run_post_earnings_review(ticker, quarter)
    return {"status": "success", "review": review}


@reports_router.post("/scan-earnings-results")
async def api_scan_earnings_results():
    """Scannt nach neuen Earnings und triggert Post-Earnings-Reviews."""
    logger.info("API Call: scan-earnings-results")
    from backend.app.memory.watchlist import get_watchlist
    from backend.app.data.fmp import get_earnings_history

    wl = await get_watchlist()
    reviews_triggered = []
    now = datetime.utcnow()

    for item in wl:
        ticker = item.get("ticker")
        if not ticker:
            continue
        try:
            history = await get_earnings_history(ticker, limit=1)
            if history and history.last_quarter:
                earnings_date = getattr(history.last_quarter, "earnings_date", None)
                if isinstance(earnings_date, datetime):
                    days_ago = abs((now - earnings_date).days)
                    if days_ago <= 3:
                        result = await run_post_earnings_review(ticker)
                        reviews_triggered.append({"ticker": ticker, "result": result})
                        logger.info(f"Post-Earnings Review getriggert für {ticker}")
        except Exception as e:
            logger.debug(f"Earnings-Scan für {ticker}: {e}")

    return {
        "status": "success",
        "reviews_triggered": len(reviews_triggered),
        "details": reviews_triggered,
    }

@data_router.get("/market-overview")
async def api_market_overview():
    """Gibt die aktuelle Marktübersicht zurück (Indizes, Sektoren, Makro)."""
    logger.info("API Call: market-overview")
    overview = await fetch_market_overview()
    return overview

app.include_router(data_router)
app.include_router(watchlist_router)
app.include_router(reports_router)

# Diagnostics Router
diagnostics_router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

@diagnostics_router.get("/db")
async def api_diagnostics_db():
    """Prüft den Datenstand aller Supabase-Tabellen."""
    from backend.app.db import get_supabase_client
    db = get_supabase_client()
    if db is None:
        return {"status": "error", "message": "Supabase nicht verbunden"}

    results = {}
    tables = ["watchlist", "short_term_memory", "daily_snapshots", "macro_snapshots", "audit_reports"]
    for table in tables:
        try:
            data = db.table(table).select("*", count="exact").limit(0).execute()
            results[table] = {"count": data.count if hasattr(data, "count") else "unknown", "status": "ok"}
        except Exception as e:
            results[table] = {"count": 0, "status": f"error: {str(e)[:100]}"}

    return {"status": "success", "tables": results}

@diagnostics_router.get("/full")
async def api_diagnostics_full():
    """Vollständiger Systemcheck aller Kafin-Komponenten."""
    import httpx
    results = {}

    # 1. Supabase
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        wl = db.table("watchlist").select("ticker").execute()
        results["supabase"] = {"status": "ok", "watchlist_count": len(wl.data)}
    except Exception as e:
        results["supabase"] = {"status": "error", "message": str(e)[:100]}

    # 2. DeepSeek
    try:
        from backend.app.analysis.deepseek import call_deepseek
        response = await call_deepseek("Antworte mit OK", "Test")
        results["deepseek"] = {"status": "ok" if response else "error"}
    except Exception as e:
        results["deepseek"] = {"status": "error", "message": str(e)[:100]}

    # 3. Finnhub
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={settings.finnhub_api_key}")
            results["finnhub"] = {"status": "ok" if r.status_code == 200 else "error", "http": r.status_code}
    except Exception as e:
        results["finnhub"] = {"status": "error", "message": str(e)[:100]}

    # 4. FMP
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"https://financialmodelingprep.com/stable/profile?symbol=AAPL&apikey={settings.fmp_api_key}")
            results["fmp"] = {"status": "ok" if r.status_code == 200 else "error", "http": r.status_code}
    except Exception as e:
        results["fmp"] = {"status": "error", "message": str(e)[:100]}

    # 5. FRED
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key={settings.fred_api_key}&limit=1&file_type=json&sort_order=desc")
            results["fred"] = {"status": "ok" if r.status_code == 200 else "error", "http": r.status_code}
    except Exception as e:
        results["fred"] = {"status": "error", "message": str(e)[:100]}

    # 6. FinBERT
    try:
        from backend.app.analysis.finbert import analyze_sentiment
        score = analyze_sentiment("Stock price increases sharply")
        results["finbert"] = {"status": "ok", "test_score": score}
    except Exception as e:
        results["finbert"] = {"status": "error", "message": str(e)[:100]}

    # 7. Telegram
    try:
        from backend.app.alerts.telegram import send_telegram_alert
        await send_telegram_alert("🧪 Systemtest")
        results["telegram"] = {"status": "ok"}
    except Exception as e:
        results["telegram"] = {"status": "error", "message": str(e)[:100]}

    # 8. n8n
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get("http://kafin-n8n:5678/healthz")
            results["n8n"] = {"status": "ok" if r.status_code == 200 else "error"}
    except Exception as e:
        results["n8n"] = {"status": "error", "message": str(e)[:100]}

    # Zusammenfassung
    all_ok = all(v.get("status") == "ok" for v in results.values())
    failed = [k for k, v in results.items() if v.get("status") != "ok"]

    return {
        "status": "all_ok" if all_ok else "issues_found",
        "failed_systems": failed,
        "details": results
    }

app.include_router(diagnostics_router)

# Telegram Test Router
telegram_router = APIRouter(prefix="/api/telegram", tags=["telegram"])

@telegram_router.post("/test")
async def api_telegram_test():
    """Sendet eine Test-Nachricht per Telegram."""
    from backend.app.alerts.telegram import send_telegram_alert
    await send_telegram_alert("🧪 Kafin Systemtest: Telegram-Verbindung OK.")
    return {"status": "success", "message": "Test-Nachricht gesendet"}

app.include_router(telegram_router)

# Logs Router
logs_router = APIRouter(prefix="/api/logs", tags=["logs"])

@logs_router.get("")
async def api_get_logs():
    """Gibt die letzten 500 Log-Einträge zurück."""
    from backend.app.logger import get_logger
    import os
    import json
    
    # Versuche Logs aus Datei zu lesen (falls vorhanden)
    log_file = os.path.join(os.path.dirname(__file__), "..", "..", "logs", "kafin.log")
    
    if not os.path.exists(log_file):
        # Fallback: generiere Mock-Logs für Development
        return [
            {"timestamp": "2026-03-18T08:00:00Z", "level": "info", "logger": "backend.app.main", "event": "Kafin gestartet"},
            {"timestamp": "2026-03-18T08:00:05Z", "level": "info", "logger": "backend.app.db", "event": "Supabase verbunden"},
            {"timestamp": "2026-03-18T08:00:10Z", "level": "warning", "logger": "backend.app.data.fmp", "event": "Rate Limit erreicht"},
        ]
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()[-500:]  # Letzte 500 Zeilen
        
        logs = []
        for line in lines:
            try:
                log_entry = json.loads(line.strip())
                logs.append(log_entry)
            except:
                continue
        
        return logs
    except Exception as e:
        logger.error(f"Fehler beim Lesen der Logs: {e}")
        return []

app.include_router(logs_router)

