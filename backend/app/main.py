"""
main — FastAPI Entrypoint

Input:  HTTP Requests (REST)
Output: HTTP Responses (JSON)
Deps:   FastAPI, config, logger, schemas, admin
Config: app_name, environment
API:    Keine externen (nur intern)
"""
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import asyncio

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
from backend.app.config import settings
from backend.app.logger import get_logger, get_recent_logs, get_module_status
from backend.app.admin import router as admin_router
from backend.app.admin.score_backfill import router as score_backfill_router
from backend.app.init_watchlist import ensure_watchlist_populated
from backend.app.init_db import (
    ensure_daily_snapshots_table,
    log_schema_extension_sql,
    get_schema_extension_sql,
    log_custom_search_terms_sql,
)
from backend.app.analysis.post_earnings_review import run_post_earnings_review
from backend.app.analysis.shadow_portfolio import (
    get_shadow_portfolio_summary,
    get_weekly_shadow_report,
)
from backend.app.memory.long_term import get_insights
from backend.app.db import get_supabase_client
from backend.app.cache import cache_get, cache_set, cache_invalidate, cache_invalidate_prefix
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
    # PostgreSQL Connection Pool initialisieren
    try:
        from backend.app.database import get_pool
        await get_pool()
        logger.info(
            "PostgreSQL Connection Pool initialisiert"
        )
    except Exception as e:
        logger.error(
            f"PostgreSQL Connection Fehler: {e}"
        )
    
    logger.info(f"Starter {settings.app_name} im [{settings.environment}] Modus.")
    logger.info("Admin Panel ist verfügbar bei /admin")
    if settings.use_mock_data:
        logger.warning("Mock-Data-Modus ist AKTIV. Es werden keine echten APIs aufgerufen.")
    await ensure_watchlist_populated()
    await ensure_daily_snapshots_table()
    log_schema_extension_sql()

    # API Usage Tabelle erstellen (einmalig)
    try:
        from backend.app.database import get_pool
        import aiofiles, os
        pool = await get_pool()
        migration = os.path.join(
            "/app/database/migrations",
            "04_api_usage.sql"
        )
        if os.path.exists(migration):
            with open(migration, "r") as f:
                sql = f.read()
            async with pool.acquire() as conn:
                await conn.execute(sql)
            logger.info("api_usage Tabelle bereit.")
    except Exception as e:
        logger.warning(f"api_usage Migration: {e}")

    # Periodischer Flush alle 5 Minuten
    async def _periodic_flush():
        while True:
            await asyncio.sleep(300)
            try:
                from backend.app.analysis.usage_tracker import (
                    flush_to_db
                )
                await flush_to_db()
            except Exception:
                pass

    asyncio.create_task(_periodic_flush())

    # Warm-Start für Market-Cache
    async def _warm():
        try:
            logger.info("Cache-Warm-Start...")
            from backend.app.data.market_overview import (
                get_market_overview,
                get_market_breadth,
                get_intermarket_signals,
            )
            # Parallel laden
            await asyncio.gather(
                get_market_overview(),
                get_market_breadth(),
                get_intermarket_signals(),
                return_exceptions=True,
            )
            logger.info("Cache-Warm-Start abgeschlossen.")
        except Exception as e:
            logger.warning(f"Warm-Start Fehler: {e}")

    # Non-blocking — läuft parallel zum Server-Start
    asyncio.create_task(_warm())

    # Embedding-Modell vorwärmen (läuft im Hintergrund)
    async def _warm_embeddings():
        try:
            from backend.app.embeddings import embed_text
            await embed_text("Kafin startup test")
            logger.info("Embedding-Modell bereit.")
        except Exception as e:
            logger.warning(
                f"Embedding-Modell nicht geladen: {e}"
            )

    asyncio.create_task(_warm_embeddings())


@app.on_event("shutdown")
async def shutdown_event():
    """Schließt externe Ressourcen sauber beim Server-Shutdown."""
    try:
        from backend.app.database import close_pool
        await close_pool()
        logger.info("PostgreSQL Connection Pool geschlossen")
    except Exception as e:
        logger.warning(f"Shutdown Pool Close Fehler: {e}")

app.include_router(admin_router)
app.include_router(score_backfill_router, prefix="/api/admin/scores", tags=["scores"])

@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Prüft, ob die API erreichbar ist."""
    return HealthCheckResponse(status="ok", version="1.0.0")


@app.post("/api/admin/init-tables")
async def api_admin_init_tables():
    """Gibt das SQL für Phase-4A Tabellen zurück."""
    sql = get_schema_extension_sql()
    logger.info("Phase-4A Tabellen SQL — bitte in Supabase ausführen:")
    logger.info("\n" + get_schema_extension_sql())
    log_custom_search_terms_sql()
    logger.info("API Call: admin init tables SQL ausgegeben")
    return {"status": "success", "sql": sql}

@app.post("/api/admin/embeddings/backfill")
async def api_embeddings_backfill(
    table: str = Query(
        "short_term_memory",
        description="Tabelle: short_term_memory | audit_reports"
    ),
    limit: int = Query(100),
):
    """
    Generiert Embeddings für Einträge ohne Embedding.
    Für Initial-Befüllung nach Migration.
    """
    if table not in (
        "short_term_memory", "audit_reports",
        "long_term_memory"
    ):
        raise HTTPException(400, "Ungültige Tabelle")

    from backend.app.database import get_pool
    from backend.app.embeddings import save_embedding

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT id, ticker, bullet_points, '
            f'report_text FROM "{table}" '
            f'WHERE embedding IS NULL '
            f'LIMIT $1',
            limit,
        )

    processed = 0
    for row in rows:
        # Text für Embedding zusammenbauen
        if table == "short_term_memory":
            bps = row.get("bullet_points") or []
            text = (
                f"{row['ticker']}: "
                + " | ".join(
                    str(b) for b in
                    (bps if isinstance(bps, list)
                     else [bps])[:3]
                )
            )
        elif table == "audit_reports":
            text = (
                f"{row.get('ticker', '')}: "
                + str(row.get("report_text", ""))[:500]
            )
        else:
            text = str(row.get("insight", ""))

        ok = await save_embedding(
            table, str(row["id"]), text
        )
        if ok:
            processed += 1

    return {
        "processed": processed,
        "total":     len(rows),
        "table":     table,
    }

@app.get("/api/logs")
async def api_get_logs(level: str = None, limit: int = 200):
    """Gibt die letzten Log-Einträge zurück."""
    from backend.app.logger import is_expected_yfinance_error
    logs = get_recent_logs()
    if level:
        level_upper = level.upper()
        if level_upper == "IGNORE":
            logs = [
                l for l in logs
                if l.get("category") == "ignore"
                or is_expected_yfinance_error(l.get("event", ""), l.get("logger", ""))
            ]
        else:
            logs = [
                l for l in logs
                if l.get("level", "").upper() == level_upper
                and not is_expected_yfinance_error(l.get("event", ""), l.get("logger", ""))
            ]
    return logs[:limit]

@app.get("/api/logs/errors")
async def api_get_logs_errors():
    """Gibt nur Log-Einträge mit level 'error' oder 'warning' der letzten 24 Stunden zurück, maximal 50."""
    from backend.app.logger import is_expected_yfinance_error
    logs = get_recent_logs()
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)
    
    errors = []
    for log in logs:
        level = log.get("level", "").lower()
        if level in ("error", "warning", "critical"):
            try:
                event = log.get("event", "")
                if is_expected_yfinance_error(event, log.get("logger", "")):
                    continue
                ts_str = log.get("timestamp")
                if ts_str:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff:
                        errors.append({
                            "timestamp": ts_str,
                            "level": level,
                            "logger": log.get("logger", ""),
                            "event": log.get("event", ""),
                            "ticker": log.get("ticker")
                        })
            except Exception:
                continue
        if len(errors) >= 50:
            break
    return {"errors": errors, "count": len(errors)}

@app.get("/api/logs/module-status")
async def api_get_module_status():
    """Gibt den Execution-Status der sechs Kernmodule zurück."""
    return get_module_status()

@app.post("/api/logs/create-test-logs")
async def api_create_test_logs():
    """Erzeugt Test-Log-Einträge für alle Module (für Debugging)."""
    from backend.app.logger import create_test_module_logs
    create_test_module_logs()
    return {"status": "success", "message": "Test logs created for all modules"}

@app.get("/api/logs/module/{module_id}")
async def api_get_module_logs(module_id: str):
    """Gibt die letzten 20 Log-Zeilen für ein spezifisches Modul zurück."""
    from backend.app.logger import MODULES
    
    if module_id not in MODULES:
        raise HTTPException(status_code=404, detail="Module not found")
    
    config = MODULES[module_id]
    logs = get_recent_logs()
    module_logs = [
        log for log in logs
        if log.get("logger") in config["logger_names"]
    ]
    
    return {"logs": module_logs[:20]}

@app.get("/api/admin/api-usage")
async def api_usage_endpoint(days: int = 7):
    """
    Aggregierte API Usage der letzten N Tage.
    Inkl. heutige Echtzeit-Daten aus Redis.
    """
    from backend.app.analysis.usage_tracker import (
        get_today_summary,
        get_usage_summary,
    )

    today   = await get_today_summary()
    history = await get_usage_summary(days=days)

    # FMP Limit-Status
    fmp_today = sum(
        v.get("calls", 0)
        for v in today.get("fmp", {}).values()
    )
    finnhub_today = sum(
        v.get("calls", 0)
        for v in today.get("finnhub", {}).values()
    )

    return {
        "today":          today,
        "history":        history,
        "limits": {
            "fmp": {
                "used":      fmp_today,
                "limit":     250,
                "remaining": max(0, 250 - fmp_today),
                "pct":       round(fmp_today / 250 * 100),
            },
            "finnhub": {
                "used":      finnhub_today,
                "limit_per_min": 60,
                "note":      "per Minute, kein Tageslimit",
            },
            "groq": {
                "used_tokens": sum(
                    v.get("total_tokens", 0)
                    for v in today.get("groq", {}).values()
                ),
                "limit_per_day": 500000,
                "note":          "Llama 3.1 8B Free Tier",
            },
        },
    }

from backend.app.analysis.finbert import analyze_sentiment

@app.post("/api/finbert/analyze")
async def api_finbert_analyze(text: str):
    score = analyze_sentiment(text)
    return {"text": text, "sentiment_score": score}

from fastapi import APIRouter, Query
from typing import List, Optional

from backend.app.data.finnhub import (
    get_earnings_calendar, get_company_news, get_short_interest, get_insider_transactions,
    get_insider_transactions_list
)
from backend.app.data.fmp import (
    get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics
)
from backend.app.data.fred import get_macro_snapshot
from backend.app.data.yfinance_data import (
    get_risk_metrics, get_atm_implied_volatility, get_historical_volatility
)
from backend.app.analysis.scoring import calculate_quality_score, calculate_mismatch_score
from backend.app.data.google_news import (
    scan_google_news,
    get_custom_search_terms,
    add_custom_search_term,
    remove_custom_search_term,
)

from schemas.earnings import EarningsExpectation, EarningsHistorySummary
from schemas.sentiment import NewsBulletPoint, ShortInterestData, InsiderActivity
from schemas.valuation import ValuationData
from schemas.macro import MacroSnapshot
from schemas.options import OptionsData

data_router = APIRouter(prefix="/api/data", tags=["data"])
google_news_router = APIRouter(prefix="/api/google-news", tags=["google-news"])


@google_news_router.get("/scan")
async def api_google_news_scan():
    """Scannt Google News und kombiniert Topics, Custom Terms und Watchlist."""
    from backend.app.memory.watchlist import get_watchlist

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


@google_news_router.get("/search-terms")
async def api_get_search_terms():
    """Gibt alle aktiven benutzerdefinierten Suchbegriffe zurück."""
    terms = await get_custom_search_terms()
    return {"terms": terms}


@google_news_router.post("/search-terms")
async def api_add_search_term(term: str = Query(..., min_length=3), category: str = Query("custom")):
    """Fügt einen neuen Suchbegriff hinzu oder reaktiviert ihn."""
    success = await add_custom_search_term(term.strip(), category.strip() or "custom")
    return {"status": "success" if success else "error"}


@google_news_router.delete("/search-terms")
async def api_remove_search_term(term: str = Query(..., min_length=3)):
    """Deaktiviert einen bestehenden Suchbegriff."""
    success = await remove_custom_search_term(term.strip())
    return {"status": "success" if success else "error"}

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


@data_router.get("/ticker-track-record/{ticker}")
async def api_ticker_track_record(ticker: str):
    """Aggregiert historische Trefferquote eines Tickers inkl. Audit/PER-Daten."""
    normalized_ticker = ticker.upper()
    cache_key = f"track_record_{normalized_ticker}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    base_response = {"ticker": normalized_ticker, "summary": None, "history": []}

    db = get_supabase_client()
    if db is None:
        return base_response

    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None)
        except Exception:
            return None

    def _to_float(value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _derive_quarter(report_dt: Optional[datetime]) -> str:
        if not report_dt:
            return "—"
        quarter = ((report_dt.month - 1) // 3) + 1
        return f"Q{quarter}_{report_dt.year}"

    try:
        reviews_res = await (
            db.table("earnings_reviews")
            .select(
                "id,ticker,quarter,pre_earnings_score_opportunity,pre_earnings_score_torpedo,"
                "pre_earnings_recommendation,pre_earnings_report_date,actual_eps,actual_eps_consensus,"
                "actual_surprise_percent,actual_revenue,actual_revenue_consensus,stock_price_pre,"
                "stock_reaction_1d_percent,stock_reaction_5d_percent,prediction_correct,score_accuracy,"
                "review_text,lessons_learned,created_at"
            )
            .eq("ticker", normalized_ticker)
            .order("created_at", desc=True)
            .limit(8)
            .execute_async()
        )
        reviews = reviews_res.data or []
    except Exception as exc:
        logger.error(f"Track Record: earnings_reviews Fehler für {normalized_ticker}: {exc}")
        return base_response

    try:
        audits_res = await (
            db.table("audit_reports")
            .select("id,ticker,report_date,earnings_date,opportunity_score,torpedo_score,recommendation,created_at")
            .eq("ticker", normalized_ticker)
            .order("report_date", desc=True)
            .limit(8)
            .execute_async()
        )
        audit_rows = audits_res.data or []
    except Exception as exc:
        logger.error(f"Track Record: audit_reports Fehler für {normalized_ticker}: {exc}")
        audit_rows = []

    audits = [dict(row, _matched=False) for row in audit_rows]

    history: List[dict] = []

    for review in reviews:
        review_report_dt = _parse_datetime(review.get("pre_earnings_report_date"))
        matched_audit = None

        for audit in audits:
            if audit["_matched"]:
                continue
            audit_dt = _parse_datetime(audit.get("report_date"))
            if audit_dt and review_report_dt and abs((audit_dt - review_report_dt).days) < 3:
                matched_audit = audit
                audit["_matched"] = True
                break

        opportunity_score = (
            _to_float(matched_audit.get("opportunity_score"))
            if matched_audit and matched_audit.get("opportunity_score") is not None
            else _to_float(review.get("pre_earnings_score_opportunity"))
        )
        torpedo_score = (
            _to_float(matched_audit.get("torpedo_score"))
            if matched_audit and matched_audit.get("torpedo_score") is not None
            else _to_float(review.get("pre_earnings_score_torpedo"))
        )
        recommendation = (
            matched_audit.get("recommendation")
            if matched_audit and matched_audit.get("recommendation")
            else review.get("pre_earnings_recommendation")
        )

        history.append(
            {
                "quarter": review.get("quarter") or _derive_quarter(review_report_dt),
                "status": "reviewed",
                "report_date": review.get("pre_earnings_report_date") or (matched_audit.get("report_date") if matched_audit else None),
                "earnings_date": matched_audit.get("earnings_date") if matched_audit else None,
                "opportunity_score": opportunity_score,
                "torpedo_score": torpedo_score,
                "recommendation": recommendation,
                "actual_eps": _to_float(review.get("actual_eps")),
                "actual_eps_consensus": _to_float(review.get("actual_eps_consensus")),
                "actual_surprise_percent": _to_float(review.get("actual_surprise_percent")),
                "actual_revenue": _to_float(review.get("actual_revenue")),
                "actual_revenue_consensus": _to_float(review.get("actual_revenue_consensus")),
                "stock_price_pre": _to_float(review.get("stock_price_pre")),
                "stock_reaction_1d_percent": _to_float(review.get("stock_reaction_1d_percent")),
                "stock_reaction_5d_percent": _to_float(review.get("stock_reaction_5d_percent")),
                "prediction_correct": review.get("prediction_correct"),
                "score_accuracy": review.get("score_accuracy"),
                "review_text": review.get("review_text"),
                "lessons_learned": review.get("lessons_learned"),
            }
        )

    for audit in audits:
        if audit["_matched"]:
            continue
        audit_dt = _parse_datetime(audit.get("report_date"))
        history.append(
            {
                "quarter": _derive_quarter(audit_dt),
                "status": "pending",
                "report_date": audit.get("report_date"),
                "earnings_date": audit.get("earnings_date"),
                "opportunity_score": _to_float(audit.get("opportunity_score")),
                "torpedo_score": _to_float(audit.get("torpedo_score")),
                "recommendation": audit.get("recommendation"),
                "actual_eps": None,
                "actual_eps_consensus": None,
                "actual_surprise_percent": None,
                "actual_revenue": None,
                "actual_revenue_consensus": None,
                "stock_price_pre": None,
                "stock_reaction_1d_percent": None,
                "stock_reaction_5d_percent": None,
                "prediction_correct": None,
                "score_accuracy": None,
                "review_text": None,
                "lessons_learned": None,
            }
        )

    def _sort_key(entry: dict) -> datetime:
        return _parse_datetime(entry.get("report_date")) or _parse_datetime(entry.get("earnings_date")) or datetime.min

    history.sort(key=_sort_key, reverse=True)

    reviewed_entries = [entry for entry in history if entry["status"] == "reviewed"]
    prediction_entries = [entry for entry in reviewed_entries if entry["prediction_correct"] is not None]

    total_predictions = len(prediction_entries)
    correct_predictions = len([entry for entry in prediction_entries if entry["prediction_correct"] is True])
    wrong_predictions = len([entry for entry in prediction_entries if entry["prediction_correct"] is False])
    win_rate_pct = round((correct_predictions / total_predictions) * 100, 1) if total_predictions else 0.0

    streak = 0
    for entry in reviewed_entries:
        result = entry["prediction_correct"]
        if result is None:
            continue
        if streak == 0:
            streak = 1 if result else -1
        elif result and streak > 0:
            streak += 1
        elif (not result) and streak < 0:
            streak -= 1
        else:
            break

    torpedo_warnings_total = 0
    torpedo_warnings_correct = 0
    for review in reviews:
        torpedo_score = _to_float(review.get("pre_earnings_score_torpedo"))
        reaction = _to_float(review.get("stock_reaction_1d_percent"))
        if torpedo_score is None or reaction is None:
            continue
        if torpedo_score >= 6.0:
            torpedo_warnings_total += 1
            if reaction < 0:
                torpedo_warnings_correct += 1

    if torpedo_warnings_total > 0:
        ratio = round((torpedo_warnings_correct / torpedo_warnings_total) * 100)
        torpedo_msg = f"{torpedo_warnings_correct} von {torpedo_warnings_total} Torpedo-Warnungen korrekt ({ratio}%)"
    else:
        torpedo_msg = "Noch keine Torpedo-Warnungen für diesen Ticker"

    summary = {
        "total_predictions": total_predictions,
        "correct": correct_predictions,
        "wrong": wrong_predictions,
        "win_rate_pct": win_rate_pct,
        "current_streak": streak,
        "torpedo_warnings_total": torpedo_warnings_total,
        "torpedo_warnings_correct": torpedo_warnings_correct,
        "torpedo_calibration_msg": torpedo_msg,
    }

    response = {"ticker": normalized_ticker, "summary": summary, "history": history}
    cache_set(cache_key, response, ttl_seconds=300)
    return response


@data_router.get("/performance")
async def api_performance():
    """Aggregierte Trefferquote aus Supabase."""
    try:
        db = get_supabase_client()
        if db:
            result = await db.table("performance_tracking").select("*").order("period", desc=True).execute_async()
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


@data_router.get("/score-delta/{ticker}")
async def api_score_delta(ticker: str):
    """Gibt aktuelle Scores und deren Veränderung vs. gestern/letzte Woche zurück."""
    logger.info(f"API Call: score-delta for {ticker}")
    db = get_supabase_client()
    if not db:
        return {"error": "Supabase nicht verfügbar"}

    try:
        result = await (
            db.table("score_history")
            .select("*")
            .eq("ticker", ticker)
            .order("date", desc=True)
            .limit(7)
            .execute_async()
        )
        history = result.data if result and result.data else []
    except Exception as e:
        logger.error(f"Score-Delta Fehler für {ticker}: {e}")
        return {"error": str(e)}

    if not history:
        return {"ticker": ticker, "current": None, "delta_1d": None, "delta_7d": None, "history": []}

    current = history[0]
    yesterday = history[1] if len(history) > 1 else None
    last_week = history[-1] if len(history) >= 5 else None

    def calc_delta(current_val, prev_val):
        if current_val is not None and prev_val is not None:
            return round(current_val - prev_val, 2)
        return None

    def calc_price_pct(curr_price, prev_price):
        if curr_price and prev_price:
            try:
                return round(((curr_price - prev_price) / prev_price) * 100, 2)
            except ZeroDivisionError:
                return None
        return None

    delta_1d = None
    if yesterday:
        delta_1d = {
            "opportunity_score": calc_delta(current.get("opportunity_score"), yesterday.get("opportunity_score")),
            "torpedo_score": calc_delta(current.get("torpedo_score"), yesterday.get("torpedo_score")),
            "price_pct": calc_price_pct(current.get("price"), yesterday.get("price")),
        }

    delta_7d = None
    if last_week:
        delta_7d = {
            "opportunity_score": calc_delta(current.get("opportunity_score"), last_week.get("opportunity_score")),
            "torpedo_score": calc_delta(current.get("torpedo_score"), last_week.get("torpedo_score")),
        }

    return {
        "ticker": ticker,
        "current": {
            "opportunity_score": current.get("opportunity_score"),
            "torpedo_score": current.get("torpedo_score"),
            "price": current.get("price"),
            "rsi": current.get("rsi"),
            "trend": current.get("trend"),
            "date": current.get("date"),
        },
        "delta_1d": delta_1d,
        "delta_7d": delta_7d,
        "history": history,
    }


@data_router.get("/sparkline/{ticker}")
async def api_sparkline(ticker: str, days: int = 7):
    """Gibt den 7-Tage-Kursverlauf für Sparkline-Charts zurück."""
    logger.info(f"API Call: sparkline for {ticker} ({days}d)")
    cache_key = f"sparkline:{ticker.upper()}:{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{max(days, 2)}d")
        if hist.empty:
            return {"ticker": ticker, "data": []}
        data = []
        for idx, price in zip(hist.index, hist["Close"]):
            try:
                date_value = idx.date() if hasattr(idx, "date") else idx
            except Exception:
                date_value = str(idx)
            data.append({
                "date": str(date_value),
                "price": round(float(price), 2)
            })
        result = {"ticker": ticker, "data": data[-days:]}
        cache_set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        logger.debug(f"Sparkline Fehler für {ticker}: {e}")
        return {"ticker": ticker, "data": []}


@app.get("/api/shadow-portfolio")
async def api_shadow_portfolio_summary():
    cache_key = "shadow_portfolio_summary"
    cached = cache_get(cache_key)
    if cached:
        return cached
    result = await get_shadow_portfolio_summary()
    cache_set(cache_key, result, ttl_seconds=120)
    return result


@data_router.get("/quick-snapshot/{ticker}")
async def api_quick_snapshot(ticker: str):
    ticker = ticker.upper().strip()
    cache_key = f"quick_snapshot_{ticker}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    import asyncio
    from backend.app.data.yfinance_data import get_technical_setup
    from backend.app.data.fmp import get_analyst_estimates, get_earnings_history
    from backend.app.data.finnhub import get_short_interest
    from backend.app.memory.watchlist import get_watchlist

    try:
        results = await asyncio.gather(
            get_technical_setup(ticker),
            get_analyst_estimates(ticker),
            get_earnings_history(ticker, limit=4),
            get_short_interest(ticker),
            get_watchlist(),
            return_exceptions=True,
        )

        tech = results[0] if not isinstance(results[0], Exception) else None
        estimates = results[1] if not isinstance(results[1], Exception) else None
        history = results[2] if not isinstance(results[2], Exception) else None
        short_int = results[3] if not isinstance(results[3], Exception) else None
        watchlist = results[4] if not isinstance(results[4], Exception) else []

        is_on_watchlist = any(
            w.get("ticker", "").upper() == ticker
            for w in (watchlist if isinstance(watchlist, list) else [])
        )

        last_surprise = None
        last_beat = None
        avg_surprise = None
        beats_of_8 = None
        if history and not isinstance(history, Exception):
            avg_surprise = getattr(history, "avg_surprise_percent", None)
            beats_of_8 = getattr(history, "quarters_beat", None)
            last_q = getattr(history, "last_quarter", None)
            if last_q:
                last_surprise = getattr(last_q, "eps_surprise_percent", None)
                if last_surprise is not None:
                    last_beat = last_surprise > 0

        iv_rank = None
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            opts = stock.options
            if opts:
                nearest_exp = opts[0]
                chain = stock.option_chain(nearest_exp)
                calls = chain.calls
                if not calls.empty and "impliedVolatility" in calls.columns:
                    atm_iv = float(calls["impliedVolatility"].median()) * 100
                    iv_rank = round(atm_iv, 1)
        except Exception:
            pass

        # Expected Move aus IV (wie in research_dashboard)
        expected_move_pct = None
        expected_move_usd = None
        try:
            import math
            from datetime import date as _date
            iv = iv_rank / 100 if iv_rank else None
            if estimates and iv and iv > 0:
                report_date = getattr(estimates, "report_date", None)
                days_to = 1
                if report_date:
                    try:
                        d = _date.fromisoformat(str(report_date))
                        days_to = max(1, (d - _date.today()).days)
                    except Exception:
                        pass
                price_val = getattr(tech, "current_price", None)
                if price_val and price_val > 0:
                    expected_move_pct = round(
                        iv * math.sqrt(days_to / 365) * 100, 1
                    )
                    expected_move_usd = round(
                        price_val * iv * math.sqrt(days_to / 365), 2
                    )
        except Exception:
            pass

        # 30T-Performance für Buy-Rumor-Detection
        price_change_30d = None
        try:
            def _fetch_30d():
                hist = yf.Ticker(ticker).history(period="35d")
                if len(hist) >= 22:
                    c = float(hist["Close"].iloc[-1])
                    o = float(hist["Close"].iloc[-22])
                    return round(((c - o) / o) * 100, 1)
                return None
            price_change_30d = await asyncio.to_thread(_fetch_30d)
        except Exception:
            pass

        # Letztes Audit aus Supabase laden
        latest_audit = None
        try:
            from backend.app.db import get_supabase_client
            db = get_supabase_client()
            if db:
                audit_res = (
                    await db.table("audit_reports")
                    .select("report_date, recommendation, opportunity_score, torpedo_score")
                    .eq("ticker", ticker)
                    .order("report_date", desc=True)
                    .limit(1)
                    .execute_async()
                )
                if audit_res and audit_res.data:
                    latest_audit = audit_res.data[0]
        except Exception as e:
            logger.debug(f"Fehler beim Laden des letzten Audits für {ticker}: {e}")

        snapshot = {
            "ticker": ticker,
            "is_on_watchlist": is_on_watchlist,
            "price": round(tech.current_price, 2) if tech and tech.current_price else None,
            "change_pct": None,
            "rsi": round(tech.rsi_14, 1) if tech and tech.rsi_14 else None,
            "trend": tech.trend if tech else None,
            "sma_50": round(tech.sma_50, 2) if tech and tech.sma_50 else None,
            "sma_200": round(tech.sma_200, 2) if tech and tech.sma_200 else None,
            "high_52w": round(tech.high_52w, 2) if tech and getattr(tech, "high_52w", None) else None,
            "low_52w": round(tech.low_52w, 2) if tech and getattr(tech, "low_52w", None) else None,
            "next_earnings_date": str(estimates.report_date) if estimates and estimates.report_date else None,
            "report_timing": getattr(estimates, "report_timing", None) if estimates else None,
            "eps_consensus": estimates.eps_consensus if estimates else None,
            "revenue_consensus": estimates.revenue_consensus if estimates else None,
            "last_eps_surprise_pct": round(last_surprise, 1) if last_surprise is not None else None,
            "last_beat": last_beat,
            "avg_surprise_pct": round(avg_surprise, 1) if avg_surprise is not None else None,
            "beats_of_8": beats_of_8,
            "short_interest_pct": getattr(short_int, "short_interest_percent", None) if short_int else None,
            "days_to_cover": getattr(short_int, "days_to_cover", None) if short_int else None,
            "iv_approx": iv_rank,
            "latest_audit": latest_audit,
            "expected_move_pct": expected_move_pct,
            "expected_move_usd": expected_move_usd,
            "price_change_30d":  price_change_30d,
            "current_price":     getattr(tech, "current_price", None),
        }

        if snapshot["next_earnings_date"]:
            try:
                from datetime import date
                earnings_dt = date.fromisoformat(snapshot["next_earnings_date"])
                days_until = (earnings_dt - date.today()).days
                snapshot["earnings_countdown_days"] = days_until
                snapshot["earnings_today"] = days_until == 0
                snapshot["earnings_this_week"] = 0 <= days_until <= 7
            except Exception:
                snapshot["earnings_countdown_days"] = None
                snapshot["earnings_today"] = False
                snapshot["earnings_this_week"] = False

        cache_set(cache_key, snapshot, ttl_seconds=300)
        return snapshot
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "price": None}


@data_router.get("/volume-profile/{ticker}")
async def api_volume_profile(ticker: str):
    """
    Holt 20-Tage Volumen-Profil für Visualisierung.
    Returns: [{date, volume, close, change_pct, color}, ...]
    """
    ticker = ticker.upper().strip()
    
    try:
        import yfinance as yf
        import asyncio
        import pandas as pd
        
        def _fetch_volume_data():
            stock = yf.Ticker(ticker)
            hist = stock.history(period="25d")
            
            if hist.empty or len(hist) < 2:
                return []
            
            # Berechne tägliche Änderung
            hist["change_pct"] = hist["Close"].pct_change() * 100
            
            result = []
            for idx, row in hist.iterrows():
                result.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "volume": int(row["Volume"]),
                    "close": round(float(row["Close"]), 2),
                    "change_pct": round(float(row["change_pct"]), 2) if not pd.isna(row["change_pct"]) else 0,
                    "color": "green" if row["change_pct"] > 0 else "red" if row["change_pct"] < 0 else "gray"
                })
            
            return result[-20:]  # Letzte 20 Tage
        
        data = await asyncio.to_thread(_fetch_volume_data)
        
        # Durchschnittsvolumen berechnen
        avg_volume = sum(d["volume"] for d in data) / len(data) if data else 0
        
        return {
            "ticker": ticker,
            "data": data,
            "avg_volume": int(avg_volume),
        }
    except Exception as e:
        logger.error(f"Volume Profile Fehler für {ticker}: {e}")
        return {"ticker": ticker, "data": [], "avg_volume": 0}


@data_router.get("/research/{ticker}")
async def api_research_dashboard(
    ticker: str,
    force_refresh: bool = False,
    override_ticker: Optional[str] = None,
):
    """
    Aggregierter Research-Endpoint für das Trading-Dashboard.
    Liefert alle Daten für einen Ticker in einem Call.

    Cache-Strategie:
    - Technicals (Kurs, RSI, SMA):  15 Minuten
    - Fundamentals (P/E, PEG etc.): 24 Stunden
    - Earnings-History:             6 Stunden
    - News-Memory:                  1 Stunde
    - Gesamtantwort Cache:          10 Minuten

    force_refresh=True überspringt den Cache.
    """
    ticker = ticker.upper().strip()
    cache_key = f"research_dashboard_{ticker}"

    # Sektor-to-ETF Mapping für Relative Strength
    SECTOR_TO_ETF = {
        "Technology": "XLK",
        "Financial Services": "XLF",
        "Financials": "XLF",
        "Energy": "XLE",
        "Healthcare": "XLV",
        "Health Care": "XLV",
        "Utilities": "XLU",
        "Industrials": "XLI",
        "Communication Services": "XLC",
        "Communication": "XLC",
        "Consumer Cyclical": "XLY",
        "Consumer Discretionary": "XLY",
        "Consumer Defensive": "XLP",
        "Consumer Staples": "XLP",
        "Basic Materials": "XLB",
        "Materials": "XLB",
        "Real Estate": "XLRE",
    }

    # ── Ticker Resolver ────────────────────────────────────────
    from backend.app.data.ticker_resolver import resolve_ticker

    # override_ticker: User hat manuell einen anderen Ticker angegeben
    if override_ticker:
        effective_ticker = override_ticker.upper().strip()
        resolution = {
            "resolved_ticker": effective_ticker,
            "original_ticker": ticker,
            "was_resolved": effective_ticker != ticker,
            "resolution_note": f"Manuell überschrieben: {effective_ticker}",
            "data_quality": "unknown",
            "available_fields": 0,
        }
    else:
        resolution = await resolve_ticker(ticker)
        effective_ticker = resolution["resolved_ticker"]

    if not force_refresh:
        cached = cache_get(cache_key)
        if cached:
            return cached

    logger.info(f"Research Dashboard: Lade Daten für {ticker}")

    # ── Alle Daten parallel laden ──────────────────────────────
    import asyncio
    from backend.app.data.yfinance_data import (
        get_technical_setup, get_fundamentals_yf,
        get_options_metrics, get_atm_implied_volatility, get_options_oi_analysis,
    )
    from backend.app.data.fmp import (
        get_company_profile, get_key_metrics,
        get_analyst_estimates, get_earnings_history,
        get_price_target_consensus, get_analyst_grades,
    )
    from backend.app.data.finnhub import (
        get_short_interest, get_insider_transactions, get_company_news,
    )
    from backend.app.data.finra import get_finra_short_volume
    from backend.app.data.market_overview import get_market_overview
    from backend.app.data.market_overview import get_market_news_for_sentiment
    from backend.app.data.reddit_monitor import get_reddit_sentiment
    from backend.app.data.fear_greed import get_fear_greed_score
    from backend.app.memory.short_term import get_bullet_points
    from backend.app.memory.watchlist import get_watchlist
    from backend.app.utils.timezone import now_mez, mez_date_string
    from datetime import datetime, timedelta
    import datetime as _dt  # For news fallback timestamp conversion

    now = now_mez()
    month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    today_str = now.strftime("%Y-%m-%d")

    results = await asyncio.gather(
        get_technical_setup(effective_ticker),           # 0
        get_fundamentals_yf(effective_ticker),           # 1
        get_company_profile(effective_ticker),           # 2
        get_key_metrics(effective_ticker),               # 3
        get_analyst_estimates(effective_ticker),         # 4
        get_earnings_history(effective_ticker, limit=8), # 5
        get_price_target_consensus(effective_ticker),    # 6
        get_short_interest(effective_ticker),            # 7
        get_insider_transactions(effective_ticker),      # 8
        get_bullet_points(effective_ticker),             # 9
        get_watchlist(),                       # 10
        get_options_metrics(effective_ticker),           # 11
        get_company_news(effective_ticker, month_ago, today_str),  # 12
        get_market_overview(),                           # 13 - NEW for relative strength
        get_analyst_grades(effective_ticker),           # 14 - NEW for guidance_trend
        get_market_news_for_sentiment(),                 # 15 - NEW for market sentiment context
        get_options_oi_analysis(effective_ticker),       # 16 - NEW for Max Pain
        get_finra_short_volume(effective_ticker),        # 17 - NEW for FINRA Short Volume
        get_reddit_sentiment(effective_ticker),          # 18 - NEW for Reddit sentiment
        get_fear_greed_score(),                          # 19 - NEW for Fear & Greed
        return_exceptions=True,
    )

    def safe(idx):
        r = results[idx]
        return None if isinstance(r, Exception) else r

    tech       = safe(0)
    yf_fund    = safe(1)
    profile    = safe(2)
    metrics    = safe(3)
    estimates  = safe(4)
    history    = safe(5)

    # yfinance Fallback wenn FMP leer
    if (not history
        or not getattr(history, "all_quarters", None)):
        from backend.app.data.yfinance_data import (
            get_earnings_history_yf
        )
        yf_history = await get_earnings_history_yf(
            effective_ticker
        )
        if yf_history:
            # Kompatibles Objekt erstellen
            from types import SimpleNamespace
            history = SimpleNamespace(
                quarters_beat=yf_history["quarters_beat"],
                avg_surprise_percent=yf_history[
                    "avg_surprise_percent"
                ],
                all_quarters=yf_history["all_quarters"],
                last_quarter=SimpleNamespace(
                    **yf_history["all_quarters"][0]
                ) if yf_history["all_quarters"] else None,
                source="yfinance",
            )
            logger.info(
                f"Earnings-Fallback yfinance für {ticker}"
            )

    price_tgt  = safe(6)
    short_int  = safe(7)
    insiders   = safe(8)
    news_mem   = safe(9) or []
    watchlist  = safe(10) or []
    options    = safe(11)
    news_items = safe(12) or []
    market_ov  = safe(13)
    analyst_grades = safe(14) or []
    market_sent_data = safe(15) or {}
    oi_data = safe(16)
    finra_data = safe(17)
    reddit_data = safe(18)
    fg = safe(19)

    # ── Watchlist-Status ───────────────────────────────────────
    is_watchlist = any(
        w.get("ticker", "").upper() == ticker
        for w in (watchlist if isinstance(watchlist, list) else [])
    )
    watchlist_item = next(
        (w for w in watchlist if w.get("ticker", "").upper() == ticker),
        None
    )

    # ── Preis & Technicals ─────────────────────────────────────
    price = None
    change_pct = None
    try:
        if tech and not isinstance(tech, Exception):
            price = getattr(tech, "current_price", None)
            change_pct = getattr(tech, "change_1d_pct", None)
    except Exception:
        pass

    # Fallback: yf_fund wenn tech kein Preis hat
    if price is None and isinstance(yf_fund, dict):
        price = yf_fund.get("price")
        if change_pct is None:
            change_pct = yf_fund.get("change_pct")

    # Pre/Post-Market Preis
    pre_market_price = None
    post_market_price = None
    pre_market_change = None
    try:
        def _fetch_extended():
            import yfinance as yf
            fi = yf.Ticker(effective_ticker).fast_info
            pre  = getattr(fi, "pre_market_price", None)
            post = getattr(fi, "post_market_price", None)
            reg  = getattr(fi, "last_price", None)
            return (
                round(float(pre), 2) if pre else None,
                round(float(post), 2) if post else None,
                round(float(reg), 2) if reg else None,
            )
        pre_p, post_p, reg_p = await asyncio.to_thread(_fetch_extended)
        pre_market_price  = pre_p
        post_market_price = post_p
        # Pre-Market Change vs. letztem Schlusskurs
        if pre_p and reg_p and reg_p > 0:
            pre_market_change = round(
                (pre_p - reg_p) / reg_p * 100, 2
            )
        elif post_p and reg_p and reg_p > 0:
            pre_market_change = round(
                (post_p - reg_p) / reg_p * 100, 2
            )
    except Exception:
        pass

    # Letzter Fallback: fast_info (nur wenn beide fehlen)
    if price is None:
        try:
            import yfinance as yf
            def _fetch_price_fallback():
                fi = yf.Ticker(effective_ticker).fast_info
                p = getattr(fi, "last_price", None)
                c = getattr(fi, "regular_market_day_change_percent", None)
                return (
                    round(float(p), 2) if p is not None else None,
                    round(float(c) * 100, 2) if c is not None else None,
                )
            price, change_pct = await asyncio.to_thread(
                _fetch_price_fallback
            )
        except Exception:
            pass

    # ── Fundamentals zusammenführen (FMP > yfinance) ───────────
    pe_ratio = None
    forward_pe = None
    ps_ratio = None
    peg_ratio = None
    ev_ebitda = None
    debt_equity = None
    fcf_yield = None
    current_ratio = None
    market_cap = None
    beta = None
    dividend_yield = None
    revenue_ttm = None
    eps_ttm = None
    sector = None
    industry = None
    company_name = None
    fifty_two_week_high = None
    fifty_two_week_low = None
    analyst_target = None
    analyst_recommendation = None
    number_of_analysts = None

    # FMP Key Metrics (Priorität)
    if metrics:
        pe_ratio    = getattr(metrics, "pe_ratio", None)
        ps_ratio    = getattr(metrics, "ps_ratio", None)
        market_cap  = getattr(metrics, "market_cap", None)
        debt_equity = getattr(metrics, "debt_to_equity", None)
        fcf_yield   = getattr(metrics, "free_cash_flow_yield", None)
        current_ratio = getattr(metrics, "current_ratio", None)
        sector      = getattr(metrics, "sector", None)
        industry    = getattr(metrics, "industry", None)

    # yfinance Fallback + Ergänzungen
    if yf_fund:
        pe_ratio        = pe_ratio or yf_fund.get("pe_ratio")
        forward_pe      = yf_fund.get("forward_pe")
        ps_ratio        = ps_ratio or yf_fund.get("ps_ratio")
        market_cap      = market_cap or yf_fund.get("market_cap")
        beta            = yf_fund.get("beta")
        dividend_yield  = yf_fund.get("dividend_yield")
        revenue_ttm     = yf_fund.get("revenue_ttm")
        eps_ttm         = yf_fund.get("eps_ttm")
        sector          = sector or yf_fund.get("sector")
        industry        = industry or yf_fund.get("industry")
        fifty_two_week_high = yf_fund.get("fifty_two_week_high")
        fifty_two_week_low  = yf_fund.get("fifty_two_week_low")
        analyst_target        = yf_fund.get("analyst_target")
        analyst_recommendation = yf_fund.get("analyst_recommendation")
        number_of_analysts    = yf_fund.get("number_of_analysts")

    # FMP Profil
    ceo = None
    employees = None
    description = None
    website = None
    ipo_date = None
    country = None
    exchange = None
    peers_list: list[str] = []
    
    if profile:
        company_name = getattr(profile, "company_name", None)
        sector   = sector or getattr(profile, "sector", None)
        industry = industry or getattr(profile, "industry", None)

        # Company Profile Details for P1c
        ceo           = getattr(profile, "ceo", None)
        employees     = getattr(profile, "fullTimeEmployees", None) \
                        or getattr(profile, "employees", None)
        description   = getattr(profile, "description", None)
        website       = getattr(profile, "website", None)
        ipo_date      = getattr(profile, "ipoDate", None) \
                        or getattr(profile, "ipo_date", None)
        country       = getattr(profile, "country", None)
        exchange      = getattr(profile, "exchange", None)

        # Peers aus FMP (falls vorhanden)
        try:
            raw_peers = getattr(profile, "peers", None)
            if isinstance(raw_peers, list):
                peers_list = [
                    str(p).upper() for p in raw_peers[:5]
                ]
        except Exception:
            pass

    # Sektor-Peers mit Earnings nächste 14T
    sector_earnings: list[dict] = []
    try:
        from backend.app.data.finnhub import (
            get_earnings_calendar
        )
        from datetime import date, timedelta
        sector_norm = str(sector or "").strip().lower()
        if sector_norm:
            today = date.today()
            in_14 = today + timedelta(days=14)
            cal = await get_earnings_calendar(
                from_date=today.isoformat(),
                to_date=in_14.isoformat(),
            )
            if cal:
                cal_by_ticker = {}
                for item in (cal if isinstance(cal, list) else []):
                    item_ticker = (
                        getattr(item, "ticker", None)
                        or getattr(item, "symbol", None)
                        or ""
                    ).upper()
                    if item_ticker:
                        cal_by_ticker[item_ticker] = item

                for w in (watchlist if isinstance(watchlist, list) else []):
                    item_ticker = str(w.get("ticker", "")).upper()
                    if not item_ticker or item_ticker == ticker.upper():
                        continue

                    item_sector = str(w.get("sector", "")).strip().lower()
                    if item_sector != sector_norm:
                        continue

                    cal_item = cal_by_ticker.get(item_ticker)
                    if not cal_item:
                        continue

                    sector_earnings.append({
                        "ticker": item_ticker,
                        "date": getattr(cal_item, "report_date", None),
                        "timing": getattr(cal_item, "report_timing", None)
                        or getattr(cal_item, "hour", None),
                    })
    except Exception as e:
        logger.debug(f"Sektor-Kalender Fehler: {e}")

    # PEG berechnen: PE / EPS_Growth (aus FMP key-metrics wenn vorhanden)
    # FMP liefert priceEarningsToGrowthRatioTTM in key-metrics-ttm
    # Wir versuchen es aus den Rohdaten zu holen
    try:
        from backend.app.data.fmp import _fmp_get
        raw_metrics = await _fmp_get(
            "/stable/key-metrics-ttm", {"symbol": ticker}
        )
        if raw_metrics and isinstance(raw_metrics, list) and raw_metrics:
            raw = raw_metrics[0]
            peg_ratio = raw.get("priceEarningsToGrowthRatioTTM") or \
                        raw.get("pegRatioTTM")
            ev_ebitda = raw.get("enterpriseValueOverEBITDATTM") or \
                        raw.get("evToEbitdaTTM")
            # ROE und ROA ergänzen
            roe = raw.get("returnOnEquityTTM")
            roa = raw.get("returnOnAssetsTTM")
        else:
            roe = roa = None
    except Exception:
        roe = roa = None

    # ── Expected Move berechnen ────────────────────────────────
    expected_move_pct = None
    expected_move_usd = None
    try:
        import math
        from datetime import date as _date
        iv = getattr(options, "implied_volatility_atm", None) if options else None
        earnings_dt = getattr(estimates, "report_date", None) if estimates else None
        days_to_earnings = 1
        if earnings_dt:
            try:
                if hasattr(earnings_dt, "toordinal"):
                    days_to_earnings = max(1, (earnings_dt - _date.today()).days)
                else:
                    days_to_earnings = max(
                        1, (_date.fromisoformat(str(earnings_dt)) - _date.today()).days
                    )
            except Exception:
                days_to_earnings = 1
        if iv is not None and iv > 0 and price is not None and price > 0:
            expected_move_pct = round(iv * math.sqrt(days_to_earnings / 365) * 100, 1)
            expected_move_usd = round(price * iv * math.sqrt(days_to_earnings / 365), 2)
    except Exception:
        pass

    # ── Earnings-Daten ─────────────────────────────────────────
    earnings_date = None
    report_timing = None
    eps_consensus = None
    revenue_consensus = None
    beats_of_8 = None
    avg_surprise = None
    last_surprise_pct = None
    last_beat = None
    quarterly_history = []

    if estimates:
        earnings_date     = str(getattr(estimates, "report_date", None) or "")
        report_timing     = getattr(estimates, "report_timing", None)
        eps_consensus     = getattr(estimates, "eps_consensus", None)
        revenue_consensus = getattr(estimates, "revenue_consensus", None)

    if history:
        beats_of_8   = getattr(history, "quarters_beat", None)
        avg_surprise = getattr(history, "avg_surprise_percent", None)
        last_q = getattr(history, "last_quarter", None)
        if last_q:
            last_surprise_pct = getattr(last_q, "eps_surprise_percent", None)
            last_surprise_pct = (
                float(last_surprise_pct)
                if last_surprise_pct is not None else None
            )
            last_beat = bool((last_surprise_pct or 0) > 0)
        if beats_of_8 is not None:
            try:
                beats_of_8 = int(beats_of_8)
            except Exception:
                pass
        if avg_surprise is not None:
            try:
                avg_surprise = float(avg_surprise)
            except Exception:
                pass
        # Letzte 8 Quartale für Tabelle
        all_q = getattr(history, "all_quarters", [])
        for q in all_q[:8]:
            eps_actual = getattr(q, "eps_actual", None)
            eps_consensus = getattr(q, "eps_consensus", None)
            surprise_pct = getattr(q, "eps_surprise_percent", None)
            reaction_1d = getattr(q, "stock_reaction_1d", None)
            quarterly_history.append({
                "quarter": getattr(q, "quarter", ""),
                "eps_actual": float(eps_actual) if eps_actual is not None else None,
                "eps_consensus": float(eps_consensus) if eps_consensus is not None else None,
                "surprise_pct": float(surprise_pct) if surprise_pct is not None else None,
                "reaction_1d": float(reaction_1d) if reaction_1d is not None else None,
            })

    # ── Tage bis Earnings ──────────────────────────────────────
    earnings_countdown = None
    earnings_today = False
    if earnings_date:
        try:
            from datetime import date as _date2
            ed = _date2.fromisoformat(earnings_date)
            earnings_countdown = (ed - _date2.today()).days
            earnings_today = earnings_countdown == 0
        except Exception:
            pass

    # ── 30-Tage Kursperformance ────────────────────────────────
    price_change_30d = None
    try:
        if tech and not isinstance(tech, Exception):
            price_change_30d = getattr(tech, "change_1m_pct", None)
            if price_change_30d is None:
                # Fallback: aus yf_fund wenn vorhanden
                price_change_30d = (
                    yf_fund.get("change_1m_pct")
                    if isinstance(yf_fund, dict) else None
                )
    except Exception:
        price_change_30d = None

    # ── Relative Stärke berechnen ───────────────────────────────
    market_ov = market_ov or {}
    indices_data = market_ov.get("indices", {})
    sector_ranking = {
        s["symbol"]: s
        for s in market_ov.get("sector_ranking_5d", [])
    }

    spy_data = indices_data.get("SPY", {})

    # Sektor-ETF für diesen Ticker
    sector_etf_symbol = SECTOR_TO_ETF.get(sector or "", None)
    sector_etf_data = (
        sector_ranking.get(sector_etf_symbol, {})
        if sector_etf_symbol else {}
    )
    # sector_ranking_5d hat nur perf_5d — für 1d und 1m
    # nutze indices_data falls ETF dort vorhanden
    sector_etf_full = indices_data.get(sector_etf_symbol, {})

    def relative_strength(ticker_pct, bench_pct):
        if ticker_pct is None or bench_pct is None:
            return None
        return round(ticker_pct - bench_pct, 2)

    # 5-Tage Performance für den Ticker (falls vorhanden)
    price_change_5d = None
    try:
        if tech and not isinstance(tech, Exception):
            price_change_5d = getattr(tech, "change_5d_pct", None)
            if price_change_5d is None:
                price_change_5d = (
                    yf_fund.get("change_5d_pct")
                    if isinstance(yf_fund, dict) else None
                )
    except Exception:
        price_change_5d = None

    rel_strength = {
        "vs_spy_1d": relative_strength(
            change_pct, spy_data.get("change_1d_pct")
        ),
        "vs_spy_5d": relative_strength(
            price_change_5d, spy_data.get("change_5d_pct")
        ),
        "vs_spy_1m": relative_strength(
            price_change_30d, spy_data.get("change_1m_pct")
        ),
        "vs_sector_1d": relative_strength(
            change_pct, sector_etf_full.get("change_1d_pct")
        ),
        "vs_sector_5d": relative_strength(
            price_change_5d,
            sector_etf_full.get("change_5d_pct")
            or sector_etf_data.get("perf_5d")
        ),
        "vs_sector_1m": relative_strength(
            price_change_30d, sector_etf_full.get("change_1m_pct")
        ),
        "spy_1d": spy_data.get("change_1d_pct"),
        "spy_5d": spy_data.get("change_5d_pct"),
        "spy_1m": spy_data.get("change_1m_pct"),
        "sector_etf": sector_etf_symbol,
        "sector_1d": sector_etf_full.get("change_1d_pct"),
        "sector_5d": sector_etf_full.get("change_5d_pct")
                     or sector_etf_data.get("perf_5d"),
        "sector_1m": sector_etf_full.get("change_1m_pct"),
    }

    # Einordnung
    outperf_count = sum(1 for v in [
        rel_strength["vs_spy_1d"],
        rel_strength["vs_spy_5d"],
        rel_strength["vs_sector_5d"],
    ] if v is not None and v > 0)

    if outperf_count >= 3:
        rel_strength["label"] = "Stark outperformend"
        rel_strength["signal"] = "bullish"
    elif outperf_count >= 2:
        rel_strength["label"] = "Leicht outperformend"
        rel_strength["signal"] = "neutral"
    elif outperf_count == 1:
        rel_strength["label"] = "Leicht underperformend"
        rel_strength["signal"] = "neutral"
    else:
        rel_strength["label"] = "Underperformend"
        rel_strength["signal"] = "bearish"

    # ── Short Interest & Insider ───────────────────────────────
    short_interest_pct = None
    days_to_cover = None
    squeeze_risk = None
    if short_int:
        short_interest_pct = getattr(short_int, "short_interest_percent", None)
        days_to_cover      = getattr(short_int, "days_to_cover", None)
        squeeze_risk       = getattr(short_int, "squeeze_risk", None)

    # yfinance Fallback wenn Finnhub nichts liefert
    if not short_interest_pct:
        try:
            from backend.app.data.yfinance_data import get_short_interest_yf
            yf_si = await get_short_interest_yf(effective_ticker)
            if yf_si:
                short_interest_pct = yf_si.get("short_interest_percent")
                days_to_cover      = yf_si.get("short_ratio") or days_to_cover
        except Exception:
            pass

    insider_buys = 0
    insider_sells = 0
    insider_buy_value = 0.0
    insider_sell_value = 0.0
    insider_assessment = "normal"
    if insiders:
        insider_buys      = getattr(insiders, "total_buys", 0) or 0
        insider_sells     = getattr(insiders, "total_sells", 0) or 0
        insider_buy_value  = getattr(insiders, "total_buy_value", 0.0) or 0.0
        insider_sell_value = getattr(insiders, "total_sell_value", 0.0) or 0.0
        insider_assessment = getattr(insiders, "assessment", "normal") or "normal"

    # ── News-Stichpunkte (max 10 neueste) ─────────────────────
    news_bullets = []

    # Primär: FinBERT-verarbeitete Bullets aus Supabase (Watchlist-Ticker)
    for b in (news_mem or [])[:8]:
        news_bullets.append({
            "text": b.get("bullet_text", "") or b.get("insight", ""),
            "sentiment": b.get("sentiment_score", 0),
            "is_material": b.get("is_material", False),
            "category": b.get("category", "News"),
            "date": b.get("date", "") or b.get("created_at", ""),
            "source": "finbert",
        })

    # Fallback/Ergänzung: Rohe Finnhub-News wenn < 5 Bullets vorhanden
    if len(news_bullets) < 5 and news_items:
        for item in (news_items or [])[:8]:
            headline = item.get("headline", "") if isinstance(item, dict) else ""
            if not headline:
                continue
            published = item.get("datetime", 0)
            date_str = (
                _dt.datetime.fromtimestamp(published).strftime("%Y-%m-%d")
                if published else ""
            )
            news_bullets.append({
                "text": headline,
                "sentiment": 0,
                "is_material": False,
                "category": item.get("category", "News"),
                "date": date_str,
                "source": "finnhub",
                "url": item.get("url", ""),
            })

    # ── Price Target ───────────────────────────────────────────
    price_target_high = None
    price_target_low  = None
    price_target_avg  = None
    if price_tgt:
        price_target_high = price_tgt.get("targetHigh") or \
                           price_tgt.get("targetHighPrice")
        price_target_low  = price_tgt.get("targetLow") or \
                           price_tgt.get("targetLowPrice")
        price_target_avg  = price_tgt.get("targetConsensus") or \
                           price_tgt.get("targetMeanPrice")
    if not price_target_avg and analyst_target:
        price_target_avg = analyst_target

    # ── Technicals zusammenführen ──────────────────────────────
    rsi = None
    trend = None
    sma_50 = None
    sma_200 = None
    above_sma50 = None
    above_sma200 = None
    sma50_distance = None
    sma200_distance = None
    support = None
    resistance = None
    distance_52w_high = None
    sma_20 = None
    atr_14 = None
    macd = None
    macd_signal_val = None
    macd_histogram = None
    macd_bullish = None
    obv = None
    obv_trend = None
    rvol = None
    float_shares = None
    avg_volume = None
    bid_ask_spread = None

    if tech:
        rsi          = getattr(tech, "rsi_14", None)
        trend        = getattr(tech, "trend", None)
        sma_50       = getattr(tech, "sma_50", None)
        sma_200      = getattr(tech, "sma_200", None)
        above_sma50  = getattr(tech, "above_sma50", None)
        above_sma200 = getattr(tech, "above_sma200", None)
        sma50_distance  = getattr(tech, "sma50_distance_pct", None)
        sma200_distance = getattr(tech, "sma200_distance_pct", None)
        support     = getattr(tech, "support_level", None)
        resistance  = getattr(tech, "resistance_level", None)
        distance_52w_high = getattr(tech, "distance_to_52w_high_percent", None)
        sma_20            = getattr(tech, "sma_20", None)
        atr_14            = getattr(tech, "atr_14", None)
        macd              = getattr(tech, "macd", None)
        macd_signal_val   = getattr(tech, "macd_signal", None)
        macd_histogram    = getattr(tech, "macd_histogram", None)
        macd_bullish      = getattr(tech, "macd_bullish", None)
        obv               = getattr(tech, "obv", None)
        obv_trend         = getattr(tech, "obv_trend", None)
        rvol              = getattr(tech, "rvol", None)
        float_shares      = getattr(tech, "float_shares", None)
        avg_volume        = getattr(tech, "avg_volume", None)
        bid_ask_spread    = getattr(tech, "bid_ask_spread", None)

    # ── Letzter Audit aus Supabase ─────────────────────────────
    last_audit = None
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if db:
            res = (
                await db.table("audit_reports")
                .select("report_date, recommendation, opportunity_score, torpedo_score, report_text")
                .eq("ticker", ticker)
                .order("report_date", desc=True)
                .limit(1)
                .execute_async()
            )
            rows = res.data if res and res.data else []
            if rows:
                last_audit = {
                    "date": rows[0].get("report_date"),
                    "recommendation": rows[0].get("recommendation"),
                    "opportunity_score": rows[0].get("opportunity_score"),
                    "torpedo_score": rows[0].get("torpedo_score"),
                    "report_text": rows[0].get("report_text", "")[:500],
                }
    except Exception as e:
        logger.debug(f"Research: last audit {ticker}: {e}")

    # ── Sentiment-Berechnung ───────────────────────────────────────
    from backend.app.memory.short_term import _calc_sentiment_from_bullets
    
    ticker_sent = _calc_sentiment_from_bullets(news_mem or [])
    
    # Markt-Sentiment aus category_sentiment
    # (Ø aller Kategorien = Gesamt-Marktlage)
    mkt_cat = market_sent_data.get("category_sentiment", {})
    mkt_scores = [
        v.get("score", 0.0)
        for v in mkt_cat.values()
        if v.get("score") is not None
    ]
    market_avg_sentiment = round(
        sum(mkt_scores) / len(mkt_scores), 3
    ) if mkt_scores else 0.0
    
    # Sentiment-Divergenz:
    # Ticker historisch positiv aber aktuelle Trend neg
    sentiment_divergence_calc = bool(
        ticker_sent["count"] > 0
        and ticker_sent["avg"] > 0.1
        and ticker_sent["trend"] == "deteriorating"
    )
    sentiment_has_material = bool(ticker_sent["has_material"])

    # ── Data Context für Scoring ────────────────────────────────────────────────
    from backend.app.analysis.scoring import (
        calculate_opportunity_score,
        calculate_torpedo_score,
        get_recommendation,
    )
    from backend.app.data.fred import get_macro_snapshot

    opp_score_obj = None
    torp_score_obj = None
    recommendation_obj = None

    try:
        # Makro für Torpedo (VIX, Credit Spread)
        macro_snap = await get_macro_snapshot()

        # Valuation-Context — identisch wie in report_generator.py
        if metrics:
            valuation_ctx = metrics.dict() if hasattr(metrics, "dict") else {}
        elif profile:
            valuation_ctx = profile.dict() if hasattr(profile, "dict") else {}
        elif yf_fund:
            valuation_ctx = {
                "ticker": effective_ticker,
                "pe_ratio": yf_fund.get("pe_ratio"),
                "ps_ratio": yf_fund.get("ps_ratio"),
                "market_cap": yf_fund.get("market_cap"),
                "sector": yf_fund.get("sector"),
            }
        else:
            valuation_ctx = {}

        # Technicals-Context
        tech_ctx = {}
        if tech:
            tech_ctx = tech.dict() if hasattr(tech, "dict") else {}

        # Short Interest — research hat Finnhub-Objekt oder yfinance-dict
        si_ctx = {}
        if short_int:
            si_ctx = short_int.dict() if hasattr(short_int, "dict") else {}

        # Insider Activity
        ia_ctx = {}
        if insiders:
            ia_ctx = insiders.dict() if hasattr(insiders, "dict") else {}

        # Options
        opt_ctx = {}
        if options:
            opt_ctx = options.dict() if hasattr(options, "dict") else {}
            # Scoring erwartet put_call_ratio_oi — stelle sicher dass es da ist
            if "put_call_ratio_oi" not in opt_ctx and "put_call_ratio" in opt_ctx:
                opt_ctx["put_call_ratio_oi"] = opt_ctx["put_call_ratio"]

        # News Memory (FinBERT Bullets)
        news_ctx = news_mem or []

        # History — scoring erwartet quarters_beat, avg_surprise_percent
        hist_ctx = {}
        if history:
            hist_ctx = history.dict() if hasattr(history, "dict") else {}

        data_ctx = {
            "earnings_history": hist_ctx,
            "valuation": valuation_ctx,
            "short_interest": si_ctx,
            "insider_activity": ia_ctx,
            "macro": macro_snap.dict() if hasattr(macro_snap, "dict") else {},
            "technicals": tech_ctx,
            "news_memory": news_ctx,
            "options": opt_ctx,
            "web_sentiment_score": 0.0,   # Tavily nicht im Research-Endpoint
            "finbert_sentiment": ticker_sent["avg"],
            "sentiment_divergence": sentiment_divergence_calc,
            # NEU: für guidance_trend + deceleration
            "analyst_grades": analyst_grades or [],
            # NEU: für sector_regime
            "sector_ranking": market_ov.get("sector_ranking_5d", []) if market_ov else [],
            "ticker_sector": sector or "Unknown",
            # NEU: Reddit sentiment für scoring integration
            "reddit_sentiment": reddit_data.get("avg_score") if reddit_data else None,
            "reddit_mentions": reddit_data.get("mention_count", 0) if reddit_data else 0,
        }

        opp_score_obj = await calculate_opportunity_score(
            effective_ticker, data_ctx
        )
        torp_score_obj = await calculate_torpedo_score(
            effective_ticker, data_ctx
        )
        recommendation_obj = await get_recommendation(
            opp_score_obj, torp_score_obj
        )

    except Exception as e:
        logger.warning(f"Research Scoring {effective_ticker}: {e}")

    # ── Response zusammenbauen ─────────────────────────────────
    response = {
        "ticker": ticker,
        "resolved_ticker": effective_ticker,
        "was_resolved": resolution["was_resolved"],
        "resolution_note": resolution["resolution_note"],
        "data_quality": resolution["data_quality"],
        "available_fields": resolution["available_fields"],
        "company_name": company_name or ticker,
        "sector": sector,
        "industry": industry,
        "fetched_at": now.isoformat(),

        # Company Profile (P1c)
        "company_profile": {
            "ceo":       ceo,
            "employees": int(employees) if employees else None,
            "description": (
                description[:300].rsplit(" ", 1)[0] + "…"
                if description and len(description) > 300
                else description
            ),
            "website":   website,
            "ipo_date":  str(ipo_date) if ipo_date else None,
            "country":   country,
            "exchange":  exchange,
            "peers":     peers_list,
        },

        # Preis & Performance
        "price": price,
        "change_pct": change_pct,
        "price_change_30d": price_change_30d,
        "price_change_5d": price_change_5d,
        "fifty_two_week_high": fifty_two_week_high,
        "fifty_two_week_low": fifty_two_week_low,
        "pre_market_price": pre_market_price,
        "post_market_price": post_market_price,
        "pre_market_change": pre_market_change,

        # Relative Stärke
        "relative_strength": rel_strength,

        # Bewertung
        "pe_ratio": pe_ratio,
        "forward_pe": forward_pe,
        "ps_ratio": ps_ratio,
        "peg_ratio": round(peg_ratio, 2) if peg_ratio else None,
        "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda else None,
        "market_cap": market_cap,
        "beta": beta,
        "dividend_yield": dividend_yield,
        "revenue_ttm": revenue_ttm,
        "eps_ttm": eps_ttm,
        "roe": round(roe * 100, 1) if roe else None,
        "roa": round(roa * 100, 1) if roa else None,
        "debt_equity": debt_equity,
        "fcf_yield": round(fcf_yield * 100, 2) if fcf_yield else None,
        "current_ratio": current_ratio,

        # Analyst
        "analyst_target": price_target_avg or analyst_target,
        "analyst_target_high": price_target_high,
        "analyst_target_low": price_target_low,
        "analyst_recommendation": analyst_recommendation,
        "number_of_analysts": number_of_analysts,

        # Technicals
        "rsi": rsi,
        "trend": trend,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "above_sma50": above_sma50,
        "above_sma200": above_sma200,
        "sma50_distance_pct": sma50_distance,
        "sma200_distance_pct": sma200_distance,
        "support": support,
        "resistance": resistance,
        "distance_52w_high_pct": distance_52w_high,
        "sma_20": sma_20,
        "atr_14": atr_14,
        "macd": macd,
        "macd_signal": macd_signal_val,
        "macd_histogram": macd_histogram,
        "macd_bullish": macd_bullish,
        "obv_trend": obv_trend,
        "rvol": rvol,
        "float_shares": float_shares,
        "avg_volume": avg_volume,
        "bid_ask_spread": bid_ask_spread,

        # Options
        "iv_atm": round(getattr(options, "implied_volatility_atm", 0) * 100, 1) if options else None,
        "put_call_ratio": getattr(options, "put_call_ratio_vol", getattr(options, "put_call_ratio_oi", None)) if options else None,
        "expected_move_pct": expected_move_pct,
        "expected_move_usd": expected_move_usd,
        "max_pain": oi_data.get("nearest_max_pain") if oi_data else None,
        "options_oi_url": f"/api/data/options-oi/{effective_ticker}",

        # Short Interest
        "short_interest_pct": short_interest_pct,
        "days_to_cover": days_to_cover,
        "squeeze_risk": squeeze_risk,
        "finra_short_ratio": finra_data.get("short_volume_ratio") if finra_data else None,
        "squeeze_signal": "high" if (
            (finra_data.get("short_volume_ratio") or 0) > 0.55
            and (short_interest_pct or 0) > 10
        ) else "neutral",

        # Insider
        "insider_buys": insider_buys,
        "insider_sells": insider_sells,
        "insider_buy_value": insider_buy_value,
        "insider_sell_value": insider_sell_value,
        "insider_assessment": insider_assessment,

        # Earnings
        "earnings_date": earnings_date,
        "report_timing": report_timing,
        "earnings_countdown": earnings_countdown,
        "earnings_today": earnings_today,
        "eps_consensus": eps_consensus,
        "revenue_consensus": revenue_consensus,
        "beats_of_8": beats_of_8,
        "avg_surprise_pct": avg_surprise,
        "last_surprise_pct": last_surprise_pct,
        "last_beat": last_beat,
        "quarterly_history": quarterly_history,

        # News
        "news_bullets": news_bullets,

        # Watchlist
        "is_watchlist": is_watchlist,
        "web_prio": watchlist_item.get("web_prio") if watchlist_item else None,

        # Letzter Audit
        "last_audit": last_audit,

        # Scores
        "opportunity_score": round(opp_score_obj.total_score, 1)
            if opp_score_obj else None,
        "torpedo_score": round(torp_score_obj.total_score, 1)
            if torp_score_obj else None,
        "recommendation": recommendation_obj.recommendation
            if recommendation_obj else None,
        "recommendation_label": recommendation_obj.recommendation_label
            if recommendation_obj else None,
        "recommendation_reason": recommendation_obj.reasoning
            if recommendation_obj else None,
        # Score-Breakdown für aufklappbares Detail
        "score_breakdown": {
            "opportunity": {
                "earnings_momentum": round(opp_score_obj.earnings_momentum, 1),
                "whisper_delta": round(opp_score_obj.whisper_delta, 1),
                "valuation_regime": round(opp_score_obj.valuation_regime, 1),
                "guidance_trend": round(opp_score_obj.guidance_trend, 1),
                "technical_setup": round(opp_score_obj.technical_setup, 1),
                "sector_regime": round(opp_score_obj.sector_regime, 1),
                "short_squeeze": round(opp_score_obj.short_squeeze_potential, 1),
                "insider_activity": round(opp_score_obj.insider_activity, 1),
                "options_flow": round(opp_score_obj.options_flow, 1),
            } if opp_score_obj else {},
            "torpedo": {
                "valuation_downside": round(torp_score_obj.valuation_downside, 1),
                "expectation_gap": round(torp_score_obj.expectation_gap, 1),
                "insider_selling": round(torp_score_obj.insider_selling, 1),
                "guidance_deceleration": round(torp_score_obj.guidance_deceleration, 1),
                "leadership_instability": round(torp_score_obj.leadership_instability, 1),
                "technical_downtrend": round(torp_score_obj.technical_downtrend, 1),
                "macro_headwind": round(torp_score_obj.macro_headwind, 1),
            } if torp_score_obj else {},
        } if opp_score_obj and torp_score_obj else None,
        
        # Sentiment-Felder
        "finbert_sentiment": ticker_sent["avg"],
        "sentiment_label": ticker_sent["label"],
        "sentiment_trend": ticker_sent["trend"],
        "sentiment_has_material": sentiment_has_material,
        "sentiment_count": ticker_sent["count"],
        "sentiment_divergence": sentiment_divergence_calc,
        # S&P-500 Vergleich
        "market_sentiment_avg": market_avg_sentiment,
        "market_sentiment_detail": mkt_cat,
        "sentiment_vs_market": round(
            ticker_sent["avg"] - market_avg_sentiment, 3
        ) if (mkt_scores and ticker_sent["count"] > 0) else None,

        # Reddit Sentiment (NEU)
        "reddit_sentiment": {
            "score": reddit_data.get("avg_score")
                if reddit_data else None,
            "mentions": reddit_data.get("mention_count", 0)
                if reddit_data else 0,
            "label": reddit_data.get("label")
                if reddit_data else None,
        } if reddit_data else None,

        # Fear & Greed (NEU)
        "fear_greed": {
            "score": fg.get("score") if fg else None,
            "label": fg.get("label") if fg else None,
        } if fg else None,

        # Sektor-Peers Earnings nächste 14T
        "sector_earnings_upcoming": sector_earnings[:5],
    }

    # ── Datenvollständigkeit prüfen ────────────────────────────
    core_available = sum(1 for v in [
        price, pe_ratio, rsi, revenue_ttm, market_cap
    ] if v is not None)

    response["core_fields_available"] = core_available
    response["data_sufficient_for_ai"] = core_available >= 3

    if not response["data_sufficient_for_ai"]:
        response["ai_blocked_reason"] = (
            f"Nur {core_available}/5 Kernfelder verfügbar. "
            "Die KI-Analyse wäre auf falschen oder unvollständigen "
            "Daten basiert. Bitte alternativen Ticker eingeben "
            "(z.B. VOW3.DE statt VLKPF für Volkswagen)."
        )

    def _json_safe(value):
        if isinstance(value, dict):
            return {k: _json_safe(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_json_safe(v) for v in value]
        if isinstance(value, tuple):
            return [_json_safe(v) for v in value]
        if hasattr(value, "item") and not isinstance(value, (str, bytes)):
            try:
                return _json_safe(value.item())
            except Exception:
                pass
        return value

    response = _json_safe(response)

    cache_set(cache_key, response, ttl_seconds=600)
    return response


@data_router.get("/earnings-radar")
async def api_earnings_radar(days: int = 14):
    from datetime import datetime, timedelta
    from backend.app.data.finnhub import get_earnings_calendar
    from backend.app.memory.watchlist import get_watchlist

    cache_key = f"earnings_radar_{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    now = now_mez()
    from_date = now.strftime("%Y-%m-%d")
    to_date = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    import asyncio
    cal_result, watchlist = await asyncio.gather(
        get_earnings_calendar(from_date, to_date),
        get_watchlist(),
        return_exceptions=True,
    )

    if isinstance(cal_result, Exception):
        return {"entries": [], "error": str(cal_result)}

    watchlist = watchlist if isinstance(watchlist, list) else []

    wl_tickers = {w.get("ticker", "").upper() for w in watchlist}
    cross_signal_map: dict[str, list[str]] = {}
    for w in watchlist:
        for cs in (w.get("cross_signal_tickers") or []):
            cs_upper = cs.upper()
            if cs_upper not in cross_signal_map:
                cross_signal_map[cs_upper] = []
            cross_signal_map[cs_upper].append(w.get("ticker", "").upper())

    # Batch-Sentiment für alle Watchlist-Ticker laden
    from backend.app.memory.short_term import (
        get_bullet_points_batch,
        _calc_sentiment_from_bullets,
    )
    all_tickers = list(wl_tickers) + [
        cs for cs_list in cross_signal_map.values()
        for cs in cs_list
    ]
    bullets_by_ticker = await get_bullet_points_batch(
        all_tickers, limit_per_ticker=10
    )

    entries = []
    today_str = now.strftime("%Y-%m-%d")

    for item in (cal_result if isinstance(cal_result, list) else []):
        ticker = getattr(item, "ticker", None)
        if not ticker:
            continue
        ticker = ticker.upper()

        report_date = getattr(item, "report_date", None)
        date_str = str(report_date) if report_date else None
        if not date_str:
            continue

        try:
            from datetime import date
            dt = date.fromisoformat(date_str)
            days_until = (dt - date.today()).days
        except Exception:
            days_until = None

        # Pre-Earnings Sentiment berechnen
        pre_earnings_sentiment = None
        ticker_bullets = bullets_by_ticker.get(ticker, [])
        if ticker_bullets:
            sent = _calc_sentiment_from_bullets(ticker_bullets)
            pre_earnings_sentiment = {
                "avg": sent["avg"],
                "label": sent["label"],
                "trend": sent["trend"],
                "has_material": sent["has_material"],
                "count": sent["count"],
            }

        entry = {
            "ticker": ticker,
            "report_date": date_str,
            "report_timing": getattr(item, "report_timing", None),
            "eps_consensus": getattr(item, "eps_consensus", None),
            "revenue_consensus": getattr(item, "revenue_consensus", None),
            "is_watchlist": ticker in wl_tickers,
            "cross_signal_for": cross_signal_map.get(ticker, []),
            "is_today": date_str == today_str,
            "days_until": days_until,
            "pre_earnings_sentiment": pre_earnings_sentiment,
        }
        entries.append(entry)

    entries.sort(key=lambda e: (e.get("days_until") or 999))

    result = {
        "entries": entries,
        "total": len(entries),
        "from_date": from_date,
        "to_date": to_date,
        "watchlist_count": sum(1 for e in entries if e["is_watchlist"]),
        "today_count": sum(1 for e in entries if e["is_today"]),
    }

    cache_set(cache_key, result, ttl_seconds=600)
    return result


@app.get("/api/shadow-portfolio/trades")
async def api_shadow_portfolio_trades(status: str = "all"):
    try:
        db = get_supabase_client()
        if db is None:
            raise ValueError("Supabase nicht verfügbar")
        query = db.table("shadow_trades").select("*").order("created_at", desc=True)
        if status in ("open", "closed"):
            query = query.eq("status", status)
        result = await query.limit(100).execute_async()
        data = result.data or []
        return {"trades": data, "count": len(data)}
    except Exception as exc:  # noqa: BLE001
        return {"trades": [], "count": 0, "error": str(exc)}


@app.get("/api/shadow-portfolio/weekly-report")
async def api_shadow_portfolio_weekly():
    report = await get_weekly_shadow_report()
    return {"report": report}


from pydantic import BaseModel

class ManualTradeRequest(BaseModel):
    ticker: str
    direction: str          # "long" | "short"
    trade_reason: str       # aus Dropdown
    opportunity_score: float = 5.0
    torpedo_score: float = 5.0
    notes: str | None = None

VALID_TRADE_REASONS = [
    "IV Mismatch",
    "Sentiment Divergenz",
    "Relative Stärke",
    "Sympathy Play",
    "Earnings Beat erwartet",
    "Torpedo erkannt",
    "Technisches Breakout",
    "Contrarian Setup",
    "Reddit vs. Insider Divergenz",
    "Max Pain Magnet",
    "Short Squeeze Setup",
]

@app.post("/api/shadow/manual-trade")
async def api_manual_shadow_trade(
    req: ManualTradeRequest,
):
    """Manueller Shadow-Trade mit Trade-Grund."""
    if req.trade_reason not in VALID_TRADE_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Grund. Erlaubt: "
                   f"{VALID_TRADE_REASONS}"
        )

    from backend.app.analysis.shadow_portfolio import (
        open_shadow_trade,
    )
    # Richtung → Recommendation mapping
    rec_map = {
        "long":  "STRONG BUY",
        "short": "STRONG SELL",
    }
    ticker = req.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker darf nicht leer sein")

    direction = req.direction.strip().lower()
    if direction not in rec_map:
        raise HTTPException(
            status_code=400,
            detail="Ungültige Richtung. Erlaubt: long, short",
        )
    rec = rec_map[direction]

    result = await open_shadow_trade(
        ticker=ticker,
        recommendation=rec,
        opportunity_score=req.opportunity_score,
        torpedo_score=req.torpedo_score,
        trade_reason=req.trade_reason,
        manual_entry=True,
    )
    return result

@app.get("/api/shadow/trade-reasons")
async def api_trade_reasons():
    """Liste aller validen Trade-Gründe."""
    return {"reasons": VALID_TRADE_REASONS}


@app.post("/api/signals/scan")
async def api_signal_scan():
    """Manueller Signal-Scan für alle Watchlist-Ticker."""
    from backend.app.analysis.signal_scanner import scan_all_signals

    logger.info("API Call: signals-scan")
    signals = await scan_all_signals()
    return {
        "status": "success",
        "signals_found": len(signals),
        "signals": signals,
    }


@app.get("/api/opportunities")
async def api_opportunities(days: int = 7):
    """Scannt nach interessanten Earnings-Setups."""
    from backend.app.analysis.opportunity_scanner import scan_upcoming_opportunities

    logger.info(f"API Call: opportunities (days={days})")
    results = await scan_upcoming_opportunities(days_ahead=days)
    return {
        "status": "success",
        "count": len(results),
        "opportunities": results,
    }


@app.get("/api/chart-analysis/{ticker}")
async def api_chart_analysis(ticker: str):
    """Technische Chartanalyse mit konkreten Levels."""
    from backend.app.analysis.chart_analyst import analyze_chart

    logger.info(f"API Call: chart-analysis for {ticker}")
    return await analyze_chart(ticker)


@app.get("/api/chart-analysis-top")
async def api_chart_analysis_top(limit: int = 5):
    """Chartanalyse für die Top-N Watchlist-Ticker."""
    from backend.app.analysis.chart_analyst import analyze_top_watchlist

    logger.info(f"API Call: chart-analysis-top (limit={limit})")
    results = await analyze_top_watchlist(limit)
    return {"tickers": results}


@app.get("/api/data/ohlcv/{ticker}")
async def api_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Liefert validierte OHLCV-Daten inkl. SMA50/200 für Lightweight Charts."""
    allowed_periods = {"1mo", "3mo", "6mo", "1y", "2y"}
    allowed_intervals = {"1d", "1wk"}

    period = period if period in allowed_periods else "6mo"
    interval = interval if interval in allowed_intervals else "1d"
    if period in {"1mo", "3mo"} and interval == "1wk":
        interval = "1d"

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)

        if hist.empty:
            return {
                "ticker": ticker,
                "period": period,
                "interval": interval,
                "candles": [],
                "sma_50": [],
                "sma_200": [],
                "error": "Keine Daten",
            }

        candles = []
        for ts, row in hist.iterrows():
            candles.append(
                {
                    "time": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10],
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                }
            )

        close_series = hist["Close"]
        sma_50 = []
        if len(close_series) >= 50:
            sma_raw = close_series.rolling(50).mean()
            for ts, val in zip(hist.index, sma_raw):
                if not pd.isna(val):
                    sma_50.append({"time": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10], "value": round(float(val), 4)})

        sma_200 = []
        if len(close_series) >= 200:
            sma_raw = close_series.rolling(200).mean()
            for ts, val in zip(hist.index, sma_raw):
                if not pd.isna(val):
                    sma_200.append({"time": ts.strftime("%Y-%m-%d"), "value": round(float(val), 4)})

        return {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "candles": candles,
            "sma_50": sma_50,
            "sma_200": sma_200,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"OHLCV Error for {ticker}: {exc}")
        return {
            "ticker": ticker,
            "period": period,
            "interval": interval,
            "candles": [],
            "sma_50": [],
            "sma_200": [],
            "error": str(exc),
        }


@data_router.get("/finra-short/{ticker}")
async def api_finra_short(ticker: str):
    """FINRA Daily Short Volume für Ticker."""
    from backend.app.data.finra import get_finra_short_volume
    return await get_finra_short_volume(ticker.upper())


@data_router.get("/fear-greed")
async def api_fear_greed():
    """Composite Fear & Greed Score (0-100)."""
    from backend.app.data.fear_greed import (
        get_fear_greed_score
    )
    return await get_fear_greed_score()


@data_router.get("/reddit-sentiment/{ticker}")
async def api_reddit_sentiment(ticker: str):
    """Reddit Retail Sentiment für Ticker (1h Cache)."""
    from backend.app.data.reddit_monitor import (
        get_reddit_sentiment
    )
    return await get_reddit_sentiment(ticker.upper())


@data_router.get("/options-oi/{ticker}")
async def api_options_oi(ticker: str):
    """Max Pain + OI-Heatmap für Ticker."""
    from backend.app.data.yfinance_data import get_options_oi_analysis
    return await get_options_oi_analysis(ticker.upper())


@data_router.get("/vwap/{ticker}")
async def api_vwap(ticker: str):
    """VWAP Intraday für Ticker (2min Cache)."""
    from backend.app.data.yfinance_data import get_vwap
    return await get_vwap(ticker.upper())


@app.get("/api/data/chart-overlays/{ticker}")
async def api_chart_overlays(ticker: str):
    """Aggregiert Earnings-, Torpedo-, Narrative- und Insider-Events für Charts."""
    supabase = get_supabase_client()
    base_response = {
        "earnings_events": [],
        "torpedo_alerts": [],
        "narrative_shifts": [],
        "insider_transactions": [],
    }

    if not supabase:
        return base_response

    try:
        # Schritt 1: earnings_reviews (historisch)
        reviews = await (
            supabase.table("earnings_reviews")
            .select(
                "quarter,pre_earnings_report_date,pre_earnings_recommendation,"
                "actual_surprise_percent,stock_reaction_1d_percent"
            )
            .eq("ticker", ticker)
            .order("created_at", desc=True)
            .limit(12)
            .execute_async()
        ).data or []

        earnings_events = []
        for row in reviews:
            report_dt = row.get("pre_earnings_report_date")
            if not report_dt:
                continue
            date_str = report_dt.split("T")[0]
            surprise = row.get("actual_surprise_percent")
            label = ""
            if surprise is not None:
                label = f"{'Beat' if surprise > 0 else 'Miss'} {surprise:+.1f}%"
            else:
                label = row.get("pre_earnings_recommendation") or ""

            earnings_events.append(
                {
                    "time": date_str,
                    "type": "earnings",
                    "timing": "after_hours",
                    "eps_surprise_pct": surprise,
                    "reaction_1d_pct": row.get("stock_reaction_1d_percent"),
                    "recommendation": row.get("pre_earnings_recommendation"),
                    "label": label,
                }
            )

        # Schritt 2: audit_reports (geplante)
        audits = await (
            supabase.table("audit_reports")
            .select("report_date,earnings_date,opportunity_score,torpedo_score,recommendation")
            .eq("ticker", ticker)
            .order("report_date", desc=True)
            .limit(8)
            .execute_async()
        ).data or []

        def _parse_date(value: Optional[str]) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value.replace("Z", ""))
            except ValueError:
                try:
                    return datetime.strptime(value.split("T")[0], "%Y-%m-%d")
                except Exception:  # noqa: BLE001
                    return None

        def _date_str(dt: Optional[datetime]) -> Optional[str]:
            return dt.strftime("%Y-%m-%d") if dt else None

        # match audits to reviews
        matched_review_dates = []
        for review in reviews:
            report_dt = _parse_date(review.get("pre_earnings_report_date"))
            if report_dt:
                matched_review_dates.append(report_dt)

        for audit in audits:
            report_dt = _parse_date(audit.get("report_date"))
            has_match = False
            if report_dt:
                for rev_dt in matched_review_dates:
                    if abs((rev_dt - report_dt).days) < 5:
                        has_match = True
                        break
            if has_match:
                continue

            time_value = _parse_date(audit.get("earnings_date")) or report_dt
            if not time_value:
                continue
            earnings_events.append(
                {
                    "time": _date_str(time_value),
                    "type": "earnings",
                    "timing": "after_hours",
                    "eps_surprise_pct": None,
                    "reaction_1d_pct": None,
                    "recommendation": audit.get("recommendation"),
                    "label": audit.get("recommendation") or "",
                }
            )

        # Torpedo Alerts
        torpedo_rows = await (
            supabase.table("short_term_memory")
            .select("date,bullet_points,sentiment_score,is_material")
            .eq("ticker", ticker)
            .eq("is_material", True)
            .order("date", desc=True)
            .limit(20)
            .execute_async()
        ).data or []

        torpedo_alerts = []
        for row in torpedo_rows:
            bullet_points = row.get("bullet_points")
            text = "Material Event"
            if isinstance(bullet_points, list) and bullet_points:
                text = str(bullet_points[0])[:150]
            elif isinstance(bullet_points, dict) and bullet_points:
                first_value = next(iter(bullet_points.values()))
                text = str(first_value)[:150]
            elif isinstance(bullet_points, str):
                text = bullet_points[:150]

            score = row.get("sentiment_score")
            if score is not None and score < -0.3:
                torpedo_score = round(abs(score) * 10, 2)
            else:
                torpedo_score = 6.0

            date_val = row.get("date")
            if not date_val:
                continue
            torpedo_alerts.append(
                {
                    "time": date_val.split("T")[0],
                    "type": "torpedo",
                    "event_text": text,
                    "torpedo_score": torpedo_score,
                }
            )

        # Narrative Shifts
        narrative_rows = await (
            supabase.table("short_term_memory")
            .select("date,shift_type,shift_reasoning,bullet_points,sentiment_score,is_narrative_shift")
            .eq("ticker", ticker)
            .eq("is_narrative_shift", True)
            .order("date", desc=True)
            .limit(15)
            .execute_async()
        ).data or []

        narrative_shifts = []
        for row in narrative_rows:
            bullet_points = row.get("bullet_points")
            fallback = None
            if isinstance(bullet_points, list) and bullet_points:
                fallback = str(bullet_points[0])[:150]
            elif isinstance(bullet_points, dict) and bullet_points:
                fallback = str(next(iter(bullet_points.values())))[:150]
            elif isinstance(bullet_points, str):
                fallback = bullet_points[:150]

            summary = (row.get("shift_reasoning") or fallback or "Narrative Shift")[:150]
            date_val = row.get("date")
            if not date_val:
                continue

            narrative_shifts.append(
                {
                    "time": date_val.split("T")[0],
                    "type": "narrative_shift",
                    "shift_type": row.get("shift_type"),
                    "summary": summary[:150],
                    "sentiment_delta": row.get("sentiment_score") or 0.0,
                }
            )

        # Insider Transactions
        insider_transactions = []
        try:
            insider_data = await get_insider_transactions(ticker)
            transactions = []
            if hasattr(insider_data, "transactions"):
                transactions = getattr(insider_data, "transactions") or []
            elif isinstance(insider_data, dict):
                transactions = insider_data.get("transactions", [])

            for tx in transactions:
                date_val = tx.get("transactionDate") or tx.get("date")
                if not date_val:
                    continue
                change = tx.get("change") or 0
                direction = "buy"
                if change:
                    direction = "buy" if change > 0 else "sell"
                elif tx.get("transactionType"):
                    direction = "buy" if "p" in tx.get("transactionType", "").lower() else "sell"

                price = tx.get("transactionPrice") or tx.get("price") or 0
                amount = abs(change or 0) * price

                insider_transactions.append(
                    {
                        "time": date_val.split("T")[0],
                        "type": "insider",
                        "direction": direction,
                        "name": tx.get("name") or "Insider",
                        "role": tx.get("position") or "",
                        "amount_usd": round(amount, 2),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Insider overlay fetch error für {ticker}: {exc}")

        return {
            "earnings_events": earnings_events,
            "torpedo_alerts": torpedo_alerts,
            "narrative_shifts": narrative_shifts,
            "insider_transactions": insider_transactions,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"chart-overlays Fehler für {ticker}: {exc}")
        return base_response


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
        from backend.app.memory.short_term import get_bullet_points
        
        watchlist = await get_watchlist()
        opportunities = []
        
        for item in watchlist:
            ticker = item.get("ticker")
            
            try:
                # 1. Sentiment (letzte 7 Tage)
                news_memory = await get_bullet_points(ticker)
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
    company_name: Optional[str] = None
    sector: Optional[str] = "Unknown"
    notes: Optional[str] = ""
    cross_signals: Optional[List[str]] = []

class WatchlistItemUpdate(BaseModel):
    company_name: Optional[str] = None
    sector: Optional[str] = None
    notes: Optional[str] = None
    cross_signals: Optional[List[str]] = None
    web_prio: Optional[int] = None  # NULL=Auto, 1-4=manuell

@watchlist_router.get("")
async def api_get_watchlist():
    logger.info("API Call: get-watchlist")
    return await get_watchlist()


def _fetch_ticker_data_sync(ticker: str, entry: dict) -> dict:
    """
    Synchrone Hilfsfunktion für yfinance-Calls mit Cache.
    Wird via asyncio.to_thread() im Thread-Pool ausgeführt.
    """
    import yfinance as yf
    from datetime import datetime as dt
    from backend.app.cache import cache_get, cache_set

    # Cache-Check
    cache_key = f"yf:enriched_v2:{ticker.upper()}"
    cached_data = cache_get(cache_key)
    if cached_data:
        entry.update(cached_data)
        return entry

    stock = yf.Ticker(ticker)
    result = {}

    # --- Kursdaten via fast_info (10x schneller als stock.info) ---
    try:
        fi = stock.fast_info
        # Preis — separater Try-Block
        try:
            if fi.last_price:
                result["price"] = round(float(fi.last_price), 2)
        except Exception:
            pass
        # Change % — separater Try-Block
        try:
            val = fi.regular_market_day_change_percent
            if val is not None:
                result["change_pct"] = round(float(val) * 100, 2)
        except Exception:
            pass
        # Market Cap — separater Try-Block
        try:
            if fi.market_cap:
                result["market_cap_b"] = round(float(fi.market_cap) / 1e9, 1)
        except Exception:
            pass
    except Exception:
        pass

    # --- Einmaliger history-Call für alle Technicals ---
    try:
        hist = stock.history(period="65d")

        if len(hist) >= 2:
            # Preis-Fallback wenn fast_info fehlgeschlagen
            if not result.get("price"):
                result["price"] = round(
                    float(hist["Close"].iloc[-1]), 2
                )
                prev = float(hist["Close"].iloc[-2])
                cur  = float(hist["Close"].iloc[-1])
                if prev:
                    result["change_pct"] = round(
                        ((cur - prev) / prev) * 100, 2
                    )

        if len(hist) >= 5:
            # 5T-Performance
            c_now = float(hist["Close"].iloc[-1])
            c_5d  = float(hist["Close"].iloc[-5])
            if c_5d:
                result["change_5d_pct"] = round(
                    ((c_now - c_5d) / c_5d) * 100, 2
                )

        if len(hist) >= 15:
            # ATR(14)
            hi = hist["High"]
            lo = hist["Low"]
            cl = hist["Close"]
            tr = [
                max(
                    float(hi.iloc[i]) - float(lo.iloc[i]),
                    abs(float(hi.iloc[i]) - float(cl.iloc[i-1])),
                    abs(float(lo.iloc[i]) - float(cl.iloc[i-1])),
                )
                for i in range(1, len(hist))
            ]
            result["atr_14"] = round(
                sum(tr[-14:]) / 14, 2
            ) if len(tr) >= 14 else None

        if len(hist) >= 20:
            # RVOL
            vol_today = float(hist["Volume"].iloc[-1])
            vol_avg20 = float(
                hist["Volume"].tail(20).mean()
            )
            if vol_avg20 > 0:
                result["rvol"] = round(
                    vol_today / vol_avg20, 2
                )

        if len(hist) >= 50:
            # above_sma50
            sma50 = float(hist["Close"].tail(50).mean())
            cur   = float(hist["Close"].iloc[-1])
            result["above_sma50"] = cur > sma50

    except Exception:
        pass

    # --- Earnings-Datum via calendar ---
    try:
        calendar = getattr(stock, "calendar", None)
        if calendar is not None:
            cal_data = calendar
            if hasattr(calendar, "to_dict"):
                cal_data = {
                    k: (v.tolist() if hasattr(v, "tolist") else v)
                    for k, v in calendar.to_dict().items()
                }
            if isinstance(cal_data, dict):
                earnings_field = cal_data.get("Earnings Date")
                earnings_date = None
                if isinstance(earnings_field, list) and earnings_field:
                    earnings_date = earnings_field[0]
                elif hasattr(earnings_field, "date"):
                    earnings_date = earnings_field
                if earnings_date is not None and hasattr(earnings_date, "date"):
                    earnings_date = earnings_date.date()
                if earnings_date:
                    days_until = (earnings_date - dt.now().date()).days
                    result["earnings_date"] = str(earnings_date)
                    result["earnings_countdown"] = days_until
    except Exception:
        pass

    # iv_atm: nur laden wenn Earnings bald (≤14T)
    # und nur wenn bereits ein earnings_countdown
    # im result vorhanden ist
    try:
        countdown = result.get("earnings_countdown")
        if countdown is not None and 0 <= countdown <= 14:
            opts = stock.options
            if opts and len(opts) > 0:
                chain = stock.option_chain(opts[0])
                atm_calls = chain.calls
                cur_price = result.get("price")
                if (
                    not atm_calls.empty
                    and cur_price
                    and cur_price > 0
                ):
                    idx = (
                        (atm_calls["strike"] - cur_price)
                        .abs()
                        .idxmin()
                    )
                    iv = float(
                        atm_calls.loc[idx, "impliedVolatility"]
                        or 0
                    )
                    if iv > 0:
                        result["iv_atm"] = round(iv * 100, 1)
    except Exception:
        pass

    # --- report_timing (pre/after market) ---
    try:
        calendar = getattr(stock, "calendar", None)
        if calendar is not None:
            cal_data = calendar
            if hasattr(calendar, "to_dict"):
                cal_data = {
                    k: (v.tolist() if hasattr(v, "tolist") else v)
                    for k, v in calendar.to_dict().items()
                }
            if isinstance(cal_data, dict):
                timing_raw = cal_data.get(
                    "Earnings Call Time", ""
                )
                if timing_raw:
                    t = str(timing_raw).lower()
                    if "before" in t or "pre" in t:
                        result["report_timing"] = "pre_market"
                    elif "after" in t or "post" in t:
                        result["report_timing"] = "after_market"
    except Exception:
        pass

    # Cache für 2 Minuten speichern (RVOL soll frischer sein)
    if result:
        cache_set(cache_key, result, ttl_seconds=120)

    entry.update(result)
    return entry


def _fetch_all_scores_sync(tickers: list, db) -> dict:
    """
    Lädt score_history für alle Ticker in EINER einzigen Supabase-Query.
    Gibt ein Dict zurück: {ticker: [latest_row, ...]}
    """
    if not db or not tickers:
        return {}
    try:
        tickers_upper = list(dict.fromkeys(t.upper() for t in tickers if t))
        max_rows = len(tickers_upper) * 8  # 8 statt 7 als Puffer
        res = (
            db.table("score_history")
            .select("*")
            .in_("ticker", tickers_upper)
            .order("date", desc=True)
            .limit(max_rows)
            .execute_async()
        )
        rows = res.data if res and res.data else []

        # Gruppiere nach Ticker
        by_ticker: dict = {}
        for row in rows:
            t = row.get("ticker", "").upper()
            if t not in by_ticker:
                by_ticker[t] = []
            by_ticker[t].append(row)

        # Pro Ticker: nach Datum sortieren, nur 7 neueste behalten (für Wochendelta)
        for t in by_ticker:
            by_ticker[t].sort(
                key=lambda r: r.get("date") or "",
                reverse=True
            )
            by_ticker[t] = by_ticker[t][:7]

        # Fairness-Fallback: falls ein Ticker durch die globale Limitierung
        # unterfüllt ist, laden wir ihn einmal gezielt nach.
        for ticker in tickers_upper:
            if len(by_ticker.get(ticker, [])) >= 7:
                continue
            try:
                single_res = (
                    db.table("score_history")
                    .select("*")
                    .eq("ticker", ticker)
                    .order("date", desc=True)
                    .limit(7)
                    .execute_async()
                )
                single_rows = single_res.data if single_res and single_res.data else []
                if single_rows:
                    by_ticker[ticker] = single_rows[:7]
            except Exception:
                continue

        return by_ticker
    except Exception as e:
        logger.debug(f"_fetch_all_scores_sync error: {e}")
        return {}


async def _enrich_single(
    item: dict,
    scores_by_ticker: dict,
    bullets_by_ticker: dict | None = None,
) -> dict:
    """
    Enriched einen einzelnen Watchlist-Ticker mit Kursdaten + Scores.
    Wird parallel via asyncio.gather aufgerufen.
    """
    ticker = item.get("ticker")
    if not ticker:
        return item

    entry = dict(item)
    bullets_by_ticker = bullets_by_ticker or {}

    # web_prio aus DB beibehalten (None = Auto)
    if "web_prio" not in entry:
        entry["web_prio"] = None

    # yfinance läuft synchron → in Thread-Pool auslagern
    try:
        entry = await asyncio.to_thread(_fetch_ticker_data_sync, ticker, entry)
    except Exception as exc:
        logger.debug(f"Enrich yfinance {ticker}: {exc}")

    # Score-Deltas aus vorgeladenem scores_by_ticker Dict
    try:
        rows = scores_by_ticker.get(ticker.upper(), [])
        if rows:
            latest = rows[0]
            entry["opportunity_score"] = latest.get("opportunity_score")
            entry["torpedo_score"] = latest.get("torpedo_score")
            entry["rsi"] = latest.get("rsi")
            entry["trend"] = latest.get("trend")
            if len(rows) > 1:
                prev = rows[1]
                entry["opp_delta"] = round(
                    (latest.get("opportunity_score") or 0)
                    - (prev.get("opportunity_score") or 0), 1
                )
                entry["torp_delta"] = round(
                    (latest.get("torpedo_score") or 0)
                    - (prev.get("torpedo_score") or 0), 1
                )

            # Wochendelta: ältester der verfügbaren Rows
            if len(rows) >= 5:
                week_row = rows[min(4, len(rows)-1)]
                entry["week_opp_delta"] = round(
                    (latest.get("opportunity_score") or 0)
                    - (week_row.get("opportunity_score") or 0), 1
                )
                entry["week_torp_delta"] = round(
                    (latest.get("torpedo_score") or 0)
                    - (week_row.get("torpedo_score") or 0), 1
                )
    except Exception as exc:
        logger.debug(f"Enrich scores {ticker}: {exc}")

    # Sentiment aus vorgeladenem Batch
    try:
        ticker_bullets = bullets_by_ticker.get(
            ticker.upper(), []
        )
        if ticker_bullets:
            sent = _calc_sentiment_from_bullets(
                ticker_bullets
            )
            entry["finbert_sentiment"]     = sent["avg"]
            entry["sentiment_label"]       = sent["label"]
            entry["sentiment_trend"]       = sent["trend"]
            entry["has_material_news"]     = sent["has_material"]
            entry["sentiment_count"]       = sent["count"]
    except Exception as exc:
        logger.debug(f"Sentiment enrich {ticker}: {exc}")

    return entry


@watchlist_router.get("/enriched")
async def api_watchlist_enriched():
    """Gibt Watchlist inkl. Kurse, Scores und Earnings-Countdown zurück."""
    logger.info("API Call: watchlist-enriched")
    
    # Cache-Check für 2 Minuten
    from backend.app.cache import cache_get, cache_set
    cache_key = "watchlist:enriched:v2"
    cached_result = cache_get(cache_key)
    if cached_result:
        logger.info("Watchlist enriched Cache-Hit")
        return cached_result

    watchlist = await get_watchlist()
    db = get_supabase_client()

    # Einmalige Batch-Query für alle Scores
    tickers = list({item.get("ticker", "").upper() for item in watchlist if item.get("ticker")})
    scores_by_ticker = await asyncio.to_thread(_fetch_all_scores_sync, tickers, db)

    # Batch-Query für Sentiment-Bullets
    from backend.app.memory.short_term import (
        get_bullet_points_batch,
        _calc_sentiment_from_bullets,
    )
    bullets_by_ticker = await get_bullet_points_batch(
        tickers, limit_per_ticker=10
    )

    # ALLE Ticker parallel enrichen mit vorgeladenen Scores
    results = await asyncio.gather(
        *[_enrich_single(item, scores_by_ticker, bullets_by_ticker) for item in watchlist],
        return_exceptions=True,
    )

    enriched = []
    sectors: dict[str, int] = {}

    for r in results:
        if isinstance(r, Exception):
            logger.debug(f"Enrich gather Exception: {r}")
            continue
        entry = r
        sectors_key = entry.get("sector") or "Unknown"
        sectors[sectors_key] = sectors.get(sectors_key, 0) + 1
        enriched.append(entry)

    concentration_warning = None
    if enriched:
        dominant_sector = max(sectors, key=sectors.get)
        concentration_pct = (sectors[dominant_sector] / len(enriched)) * 100
        if concentration_pct > 60:
            concentration_warning = (
                f"⚠️ Klumpenrisiko: {concentration_pct:.0f}% der Watchlist "
                f"ist im Sektor '{dominant_sector}'. Diversifikation prüfen."
            )

    result = {
        "watchlist": enriched,
        "concentration_warning": concentration_warning,
        "sector_distribution": sectors,
    }
    
    # Cache für 2 Minuten speichern
    cache_set(cache_key, result, ttl_seconds=120)
    
    return result

@watchlist_router.post("")
async def api_add_watchlist_item(
    item: WatchlistItemCreate,
    background_tasks: BackgroundTasks,
):
    logger.info(f"API Call: add-watchlist-item {item.ticker}")
    # Wenn kein Firmenname: Ticker als Name verwenden
    company_name = item.company_name or item.ticker.upper()
    sector = item.sector or "Unknown"
    
    # Hintergrund-Task für sofortigen News-Scan
    from backend.app.data.news_processor import process_news_for_ticker

    async def _scan_and_invalidate(ticker: str):
        await process_news_for_ticker(ticker)
        cache_invalidate("watchlist:enriched:v2")
        cache_invalidate(f"research_dashboard_{ticker}")
        cache_invalidate_prefix("earnings_radar_")

    background_tasks.add_task(_scan_and_invalidate, item.ticker.upper())

    # Sofortige Cache-Invalidierung für die betroffene Watchlist
    cache_invalidate("watchlist:enriched:v2")
    
    return await add_ticker(
        item.ticker, company_name, sector,
        item.notes or "", item.cross_signals or []
    )

@watchlist_router.get("/earnings-this-week")
async def api_watchlist_earnings_this_week():
    logger.info("API Call: watchlist-earnings-this-week")
    from datetime import datetime, timedelta
    from backend.app.data.finnhub import get_earnings_calendar
    from backend.app.memory.watchlist import get_watchlist
    from backend.app.utils.timezone import now_mez

    now = now_mez()
    end_of_week = now + timedelta(days=7)
    from_date = now.strftime("%Y-%m-%d")
    to_date = end_of_week.strftime("%Y-%m-%d")
    
    cal = await get_earnings_calendar(from_date, to_date)
    wl = await get_watchlist()
    return await get_earnings_this_week(wl, cal)

@watchlist_router.put("/{ticker}")
async def api_update_watchlist_item(ticker: str, item: WatchlistItemUpdate):
    logger.info(f"API Call: update-watchlist-item {ticker}")
    # exclude_unset=True behält explizit gesendete None-Werte bei!
    update_data = item.dict(exclude_unset=True) 
    
    try:
        from backend.app.db import get_supabase_client
        db = get_supabase_client()
        if db and update_data:
            await db.table("watchlist").update(update_data).eq("ticker", ticker.upper()).execute_async()
        
        # Cache invalidieren
        from backend.app.cache import cache_invalidate
        cache_invalidate("watchlist:enriched:v2")
        
        return {"status": "success", "updated": update_data}
    except Exception as e:
        logger.error(f"Watchlist Update Error für {ticker}: {e}")
        return {"status": "error", "message": str(e)}

@watchlist_router.delete("/{ticker}")
async def api_remove_watchlist_item(ticker: str):
    logger.info(f"API Call: remove-watchlist-item {ticker}")
    
    # Cache invalidieren
    from backend.app.cache import cache_invalidate
    cache_invalidate("watchlist:enriched:v2")
    
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
    cache_invalidate("watchlist:enriched:v2")
    cache_invalidate_prefix("research_dashboard_")
    cache_invalidate_prefix("earnings_radar_")
    return {"status": "success", "results": results}

@news_router.post("/scan/{ticker}")
async def api_news_scan_ticker(ticker: str):
    """Führt die News-Pipeline für einen einzelnen Ticker aus."""
    logger.info(f"API Call: news-scan for {ticker}")
    result = await process_news_for_ticker(ticker)
    cache_invalidate("watchlist:enriched:v2")
    cache_invalidate(f"research_dashboard_{ticker.upper()}")
    cache_invalidate_prefix("earnings_radar_")
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


@news_router.post("/scan-weekend")
async def api_news_scan_weekend():
    """Wochenend-Scan: Nur Google News + Sentiment-Alerts, kein voller Ticker-Scan."""
    logger.info("API Call: news-scan-weekend")

    from backend.app.memory.watchlist import get_watchlist
    from backend.app.data.google_news import scan_google_news
    from backend.app.analysis.finbert import analyze_sentiment_batch
    from backend.app.alerts.telegram import send_telegram_alert
    from html import escape
    from backend.app.data.macro_processor import fetch_global_macro_events

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
                    if earnings_date.tzinfo is None:
                        from datetime import timezone as _tz
                        earnings_date = earnings_date.replace(tzinfo=_tz.utc)
                    from datetime import timezone as _tz
                    now = datetime.now(_tz.utc)
                    days_ago = abs((now - earnings_date).days)
                    if days_ago <= 3:
                        result = await run_post_earnings_review(ticker)
                        reviews_triggered.append({"ticker": ticker, "result": result})
                        logger.info(f"Post-Earnings Review getriggert für {ticker}")
                        
                        # Peer-Reaktions-Alert wenn Kursreaktion bekannt
                        try:
                            if isinstance(result, dict):
                                reaction = result.get("reaction_1d")
                                if reaction is not None and abs(float(reaction)) >= 2.0:
                                    from backend.app.analysis.peer_monitor import (
                                        send_peer_reaction_alert,
                                    )
                                    await send_peer_reaction_alert(
                                        reporter=ticker,
                                        move_pct=float(reaction),
                                        report_timing="after_hours",
                                    )
                        except Exception as e:
                            logger.debug(f"Peer Reaction Auto-Alert {ticker}: {e}")
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

@data_router.get("/market-breadth")
async def api_market_breadth():
    """Marktbreite: % Aktien über SMA50/200."""
    from backend.app.data.market_overview import get_market_breadth
    return await get_market_breadth()

@data_router.get("/intermarket")
async def api_intermarket():
    """Cross-Asset-Signale für Regime-Erkennung."""
    from backend.app.data.market_overview import get_intermarket_signals
    return await get_intermarket_signals()


@data_router.get("/market-news-sentiment")
async def api_market_news_sentiment():
    """Marktnachrichten mit FinBERT-Sentiment, kategorisiert."""
    from backend.app.data.market_overview import get_market_news_for_sentiment
    return await get_market_news_for_sentiment()


@data_router.get("/economic-calendar")
async def api_economic_calendar():
    """
    Wirtschaftskalender nächste 48h aus GENERAL_MACRO Ticker.
    Nutzt bestehende Finnhub Economic Calendar Integration.
    """
    logger.info("API Call: economic-calendar")
    try:
        from backend.app.db import get_supabase_client
        from datetime import datetime, timedelta
        db = get_supabase_client()
        if not db:
            return {"events": []}

        now = datetime.utcnow()
        in_48h = now + timedelta(hours=48)

        res = await (
            db.table("short_term_memory")
            .select("*")
            .eq("ticker", "GENERAL_MACRO")
            .gte("date", now.isoformat())
            .lte("date", in_48h.isoformat())
            .order("date")
            .limit(10)
            .execute_async()
        )
        rows = res.data if res and res.data else []
        events = []
        for row in rows:
            bullets = row.get("bullet_points", {})
            if isinstance(bullets, dict):
                events.append({
                    "title": bullets.get("event", "Makro-Event"),
                    "date": row.get("date"),
                    "impact": bullets.get("impact", "medium"),
                    "country": bullets.get("country", "US"),
                    "actual": bullets.get("actual"),
                    "estimate": bullets.get("estimate"),
                })
        return {"events": events}
    except Exception as e:
        logger.warning(f"Economic Calendar: {e}")
        return {"events": []}


@data_router.get("/scoring-config")
async def api_scoring_config():
    """Gibt aktuelle Scoring-Gewichtungen zurück."""
    import yaml
    import os
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "scoring.yaml"
    )
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Scoring config load error: {e}")
        return {"error": "config_not_found"}


@data_router.post("/market-audit")
async def api_market_audit():
    """
    DeepSeek bewertet den Gesamtmarkt und gibt eine
    konkrete Trading-Strategie-Empfehlung aus.
    """
    logger.info("API Call: market-audit")
    import asyncio
    from backend.app.data.market_overview import (
        get_market_overview, get_market_breadth, get_intermarket_signals, get_market_news_for_sentiment
    )
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.analysis.deepseek import call_deepseek

    overview, breadth, intermarket, macro, news_sentiment = await asyncio.gather(
        get_market_overview(),
        get_market_breadth(),
        get_intermarket_signals(),
        get_macro_snapshot(),
        get_market_news_for_sentiment(),
        return_exceptions=True,
    )

    def safe(r, default={}):
        return default if isinstance(r, Exception) else r

    overview = safe(overview, {})
    breadth = safe(breadth, {})
    intermarket = safe(intermarket, {})
    macro = safe(macro)
    news_sentiment = safe(news_sentiment, {})

    # Daten für DeepSeek aufbereiten
    indices = overview.get("indices", {})
    sectors = overview.get("sector_ranking_5d", [])
    signals = intermarket.get("signals", {})

    index_lines = []
    for sym, d in indices.items():
        if isinstance(d, dict) and not d.get("error"):
            index_lines.append(
                f"{d.get('name', sym)}: ${d.get('price', '?'):.2f} "
                f"({d.get('change_1d_pct', 0):+.1f}% heute, "
                f"{d.get('change_1m_pct', 0):+.1f}% 1M) "
                f"RSI {d.get('rsi_14', '?')} Trend: {d.get('trend', '?')}"
            )

    sector_lines = [
        f"{s['name']}: {s['perf_5d']:+.1f}%"
        for s in sectors[:11]
    ]

    breadth_text = (
        f"Marktbreite (30-Titel-Sample): "
        f"{breadth.get('pct_above_sma50', '?')}% über SMA50, "
        f"{breadth.get('pct_above_sma200', '?')}% über SMA200 | "
        f"Signal: {breadth.get('breadth_signal', '?').upper()} | "
        f"Advancing: {breadth.get('advancing', '?')}, "
        f"Declining: {breadth.get('declining', '?')}"
    )

    signal_lines = []
    for k, v in signals.items():
        if not k.endswith("_note"):
            note = signals.get(f"{k}_note", "")
            signal_lines.append(f"{k}: {v}" + (f" — {note}" if note else ""))

    # Energie-Kontext explizit
    energy_stress = signals.get("energy_stress", "neutral")
    energy_note = signals.get("energy_note", "")
    stagflation = signals.get("stagflation_warning", False)
    stagflation_note = signals.get("stagflation_note", "")

    energy_block = f"""ENERGIE-SIGNAL: {energy_stress.upper()}
{energy_note}"""

    if stagflation:
        energy_block += f"""

⚡ STAGFLATIONS-WARNUNG AKTIV:
{stagflation_note}
Konsequenz: Fed kann trotz Schwäche nicht senken.
Wachstumstitel unter doppeltem Druck (Bewertung + Zinsen)."""

    # News-Sentiment für DeepSeek
    cat_sent = news_sentiment.get("category_sentiment", {})
    news_lines = []
    for cat, sent in cat_sent.items():
        label = sent.get("label", "neutral")
        score = sent.get("score", 0.0)
        count = sent.get("count", 0)
        cat_label = {
            "fed_rates": "Fed/Zinsen",
            "macro_data": "Makro-Daten",
            "geopolitics": "Geopolitik",
            "market_general": "Allgemein",
        }.get(cat, cat)
        news_lines.append(
            f"{cat_label}: {label} ({score:+.2f}, {count} Artikel)"
        )

    # Top-Schlagzeilen mit stärkstem Sentiment
    top_headlines = news_sentiment.get("headlines", [])[:5]
    headline_lines = []
    for h in top_headlines:
        score = h.get("sentiment_score", 0.0)
        headline_lines.append(
            f"  [{score:+.2f}] {h.get('headline', '')} "
            f"({h.get('source', '')})"
        )

    macro_text = (
        f"Fed Rate: {getattr(macro, 'fed_rate', '?')}% | "
        f"VIX: {getattr(macro, 'vix', '?')} | "
        f"Credit Spread (HY): {getattr(macro, 'credit_spread_bps', '?')} | "
        f"Yield Curve (10Y-2Y): {getattr(macro, 'yield_curve_10y_2y', '?')} | "
        f"Regime: {getattr(macro, 'regime', '?')}"
    ) if macro else "Makro-Daten nicht verfügbar"

    system_prompt = (
        "Du bist ein erfahrener Senior-Marktanalyst bei einem Hedge Fund. "
        "Du analysierst das aktuelle Marktregime und gibst dem Trader "
        "eine konkrete, meinungsstarke Handlungsempfehlung auf Deutsch. "
        "Keine Floskeln. Direkt. Maximal 25 Zeilen."
    )

    prompt = f"""Analysiere das aktuelle Marktumfeld und gib dem Trader eine klare Handlungsempfehlung. Antworte auf Deutsch.
Maximal 25 Zeilen. Direkt, meinungsstark, kein Hedging.

ABSOLUTE REGEL: Empfiehle NIEMALS breite Index-Shorts (SH, PSQ, SQQQ).
Nur: Sektor-ETF-Puts, Einzeltitel-Puts, Pair-Trades, Cash-Position erhöhen.

MARKTDATEN:

INDIZES:
{chr(10).join(index_lines)}

SEKTOREN (5-Tage-Performance, stärkste zuerst):
{chr(10).join(sector_lines)}

MARKTBREITE:
{breadth_text}

CROSS-ASSET SIGNALE:
{chr(10).join(signal_lines) if signal_lines else "Keine Signale berechnet"}

MAKRO:
{macro_text}

ENERGIE & ROHSTOFFE:
{energy_block}

ROTATIONS-MUSTER:
{overview.get('rotation_story', 'Kein klares Rotationsmuster')}
Defensiv (XLU/XLV/XLP) Ø {overview.get('defensive_avg_5d', 0):+.1f}%
vs. Offensiv (XLK/XLC/XLY) Ø {overview.get('offensive_avg_5d', 0):+.1f}%

NEWS-SENTIMENT (FinBERT, letzte 24h):
{chr(10).join(news_lines) if news_lines else "Keine News-Daten"}

TOP SCHLAGZEILEN (stärkstes Sentiment):
{chr(10).join(headline_lines) if headline_lines else "Keine Headlines"}

DEINE AUFGABE:
1. REGIME: Welches Marktregime herrscht gerade? (Risk-On / Mixed / Risk-Off)
   Begründe mit konkreten Zahlen.
2. MARKTGESUNDHEIT: Ist die Stärke/Schwäche breit oder konzentriert?
   Was sagt die Marktbreite?
3. SEKTORROTATION: Wohin fließt das Geld? Was bedeutet das?
4. DIVERGENZEN: Gibt es Widersprüche zwischen den Signalen?
   (z.B. Aktien steigen aber Credit Spreads weiten sich)
5. KONKRETE EMPFEHLUNG: Was bedeutet dieses Umfeld für einen
   Earnings-Trader mit Einzelaktien-Fokus?
   - Beta erhöhen oder reduzieren?
   - Welche Sektoren meiden, welche bevorzugen?
   - Ist jetzt ein guter Zeitpunkt für neue Positionen?
6. ENERGIE & GEOPOLITIK: Wenn Energie-Schock aktiv:
   Erkläre die Transmission (Öl → Inflation → Fed →
   Zinsen → Markt). Welche Sektoren leiden,
   welche profitieren? Was bedeutet das für
   einen Earnings-Trader der nächste Woche
   Quartalszahlen erwartet?"""

    try:
        report = await call_deepseek(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=1500,
        )
        return {
            "status": "success",
            "report": report,
            "generated_at": datetime.utcnow().isoformat(),
            "data_used": {
                "indices": len(index_lines),
                "sectors": len(sector_lines),
                "breadth": breadth.get("breadth_signal"),
                "regime": getattr(macro, "regime", None),
            }
        }
    except Exception as e:
        logger.error(f"Market Audit Fehler: {e}")
        return {"status": "error", "message": str(e)}

# Web Intelligence Router
web_intel_router = APIRouter(
    prefix="/api/web-intelligence", tags=["web-intelligence"]
)

@web_intel_router.post("/batch")
async def api_web_intelligence_batch():
    """
    Nacht-Batch: Aktualisiert Web Intelligence Cache für alle
    relevanten Watchlist-Ticker (Prio 1-3).
    Wird von n8n täglich um 22:30 Uhr aufgerufen.
    Prio 4 und Ticker ohne Earnings-Termin werden übersprungen.
    """
    logger.info("API Call: web-intelligence/batch")

    # API Key prüfen
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
    from datetime import date, timedelta

    wl = await get_watchlist()
    if not wl:
        return {"status": "success", "processed": 0, "skipped": 0}

    # Earnings-Kalender der nächsten 14 Tage laden
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

    # Ticker filtern (Prio 4 raus)
    active_items = []
    for item in wl:
        ticker = item.get("ticker", "").upper()
        if not ticker:
            continue

        # Tage bis Earnings
        earnings_dt = earnings_map.get(ticker)
        days_to_earnings = None
        if earnings_dt:
            try:
                if hasattr(earnings_dt, "toordinal"):
                    days_to_earnings = (earnings_dt - today).days
                else:
                    from datetime import date as _d
                    days_to_earnings = (
                        _d.fromisoformat(str(earnings_dt)) - today
                    ).days
            except Exception:
                pass

        # Effektive Prio
        manual_prio = item.get("web_prio")
        auto_prio = _auto_prio_from_days(days_to_earnings)
        effective_prio = manual_prio if manual_prio is not None else auto_prio

        # Prio 4 überspringen
        if effective_prio == 4:
            skipped += 1
            continue

        active_items.append((item, days_to_earnings, manual_prio, effective_prio))

    # Parallel in 5er-Chunks (Tavily Rate-Limit respektieren)
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
                    force_refresh=True,  # Batch immer fresh
                )
                return {
                    "ticker": ticker,
                    "prio": effective_prio,
                    "status": "ok",
                    "snippets": len(summary.split("•")) - 1
                    if summary else 0,
                }
            except Exception as e:
                logger.warning(f"Batch Web Intel {ticker}: {e}")
                return {"ticker": ticker, "status": "error",
                        "error": str(e)}

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


@web_intel_router.post("/refresh/{ticker}")
async def api_web_intelligence_refresh(ticker: str):
    """
    Manueller Refresh für einen einzelnen Ticker.
    Ignoriert Cache (force_refresh=True).
    """
    logger.info(f"API Call: web-intelligence/refresh/{ticker}")

    if not settings.tavily_api_key:
        return {
            "status": "error",
            "reason": "TAVILY_API_KEY nicht konfiguriert",
        }

    from backend.app.data.web_search import get_web_intelligence

    # web_prio aus Watchlist lesen
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


@web_intel_router.post("/sentiment-check")
async def api_sentiment_divergence_check():
    """
    Prüft alle Watchlist-Ticker auf Sentiment-Divergenz.
    Sendet Telegram-Alert wenn Signal erkannt.
    Von n8n stündlich aufgerufen.
    """
    logger.info("API Call: web-intelligence/sentiment-check")
    from backend.app.analysis.sentiment_monitor import (
        check_sentiment_divergence,
    )
    result = await check_sentiment_divergence()
    return result


@web_intel_router.post("/peer-check")
async def api_peer_earnings_check():
    """
    Prüft ob Cross-Signal-Ticker heute/morgen reporten.
    Von n8n täglich um 08:00 und 15:00 aufgerufen.
    """
    logger.info("API Call: peer-check")
    from backend.app.analysis.peer_monitor import (
        check_peer_earnings_today,
    )
    return await check_peer_earnings_today()


@web_intel_router.post("/peer-reaction")
async def api_peer_reaction_alert(
    reporter: str,
    move_pct: float,
    report_timing: str = "after_hours",
):
    """
    Sendet Peer-Reaktions-Alert nach Earnings eines Tickers.
    Manuell oder von Post-Earnings-Review getriggert.
    """
    logger.info(f"API Call: peer-reaction {reporter} {move_pct:+.1f}%")
    from backend.app.analysis.peer_monitor import (
        send_peer_reaction_alert,
    )
    return await send_peer_reaction_alert(
        reporter=reporter,
        move_pct=move_pct,
        report_timing=report_timing,
    )


@web_intel_router.get("/cache/{ticker}")
async def api_web_intelligence_cache(ticker: str):
    """Gibt gecachte Web Intelligence für einen Ticker zurück."""
    try:
        from backend.app.db import get_supabase_client
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


@data_router.post("/sympathy-check/{reporter}")
async def api_sympathy_check(
    reporter: str,
    move_pct: float,
):
    """
    Analysiert Peer-Reaktionen nach Earnings.
    Aufruf: POST /api/data/sympathy-check/ASML?move_pct=-5.2
    """
    from backend.app.analysis.peer_monitor import (
        check_sympathy_reactions,
        send_sympathy_alert,
    )
    from backend.app.memory.watchlist import get_watchlist

    wl = await get_watchlist()
    # Cross-Signals für Reporter aus Watchlist
    peers: list[str] = []
    for item in (wl if isinstance(wl, list) else []):
        cs = (
            item.get("cross_signal_tickers")
            or item.get("cross_signals")
            or []
        )
        if reporter.upper() in [
            c.upper() for c in cs
        ]:
            peers.append(item["ticker"])
        # Auch umgekehrt: Reporter ist in Watchlist
        if item.get("ticker", "").upper() == reporter.upper():
            peers.extend([
                c.upper() for c in cs
            ])

    peers = list(set(peers))  # Deduplizieren
    analysis = await check_sympathy_reactions(
        reporter.upper(), move_pct, peers
    )
    await send_sympathy_alert(analysis)
    return analysis


@data_router.get("/rag/similar-news")
async def api_rag_similar_news(
    query: str = Query(..., min_length=5),
    ticker: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Semantische Suche in News-Stichpunkten.
    Findet ähnliche historische News zu einer Anfrage.

    Beispiel:
      /api/data/rag/similar-news?query=CFO+tritt+zurück
      → Findet ähnliche Führungswechsel-News
    """
    from backend.app.embeddings import embed_text
    from backend.app.database import get_pool

    vec = await embed_text(query)
    if vec is None:
        return {
            "results": [],
            "error": "Embedding-Modell nicht verfügbar"
        }

    vec_str = (
        "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    )

    pool = await get_pool()
    async with pool.acquire() as conn:
        if ticker:
            rows = await conn.fetch(
                """
                SELECT ticker, date, bullet_points,
                  sentiment_score, category,
                  1 - (embedding <=> $1::vector) AS similarity
                FROM short_term_memory
                WHERE embedding IS NOT NULL
                  AND ticker = $2
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                vec_str, ticker.upper(), limit,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT ticker, date, bullet_points,
                  sentiment_score, category,
                  1 - (embedding <=> $1::vector) AS similarity
                FROM short_term_memory
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                vec_str, limit,
            )

    results = []
    for row in rows:
        bps = row["bullet_points"]
        results.append({
            "ticker":          row["ticker"],
            "date":            row["date"].isoformat()
                               if row["date"] else None,
            "bullet_points":   bps,
            "sentiment_score": row["sentiment_score"],
            "category":        row["category"],
            "similarity":      round(
                float(row["similarity"]), 3
            ),
        })

    return {
        "query":   query,
        "results": results,
        "count":   len(results),
    }


@data_router.get("/rag/similar-audits")
async def api_rag_similar_audits(
    query: str = Query(..., min_length=5),
    limit: int = Query(3, ge=1, le=10),
):
    """
    Findet historische Audit-Reports ähnlich
    zur Anfrage. Nützlich für Muster-Erkennung:
    "Zeig ähnliche Setups wie dieses"
    """
    from backend.app.embeddings import embed_text
    from backend.app.database import get_pool

    vec = await embed_text(query)
    if vec is None:
        return {"results": [], "error": "Kein Embedding"}

    vec_str = (
        "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
    )

    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ticker, report_date,
              recommendation, opportunity_score,
              torpedo_score,
              LEFT(report_text, 300) AS preview,
              1 - (embedding <=> $1::vector) AS similarity
            FROM audit_reports
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vec_str, limit,
        )

    return {
        "query":   query,
        "results": [dict(r) for r in rows],
    }


app.include_router(admin_router)
app.include_router(data_router)
app.include_router(google_news_router)
app.include_router(reports_router)
app.include_router(watchlist_router)
app.include_router(web_intel_router)

# --- LOG MANAGEMENT ---
@app.get("/api/logs/file")
async def get_file_logs(lines: int = 1000, level: str | None = None):
    from backend.app.logger import LOG_FILE, is_expected_yfinance_error
    if not os.path.exists(LOG_FILE): return {"logs": [], "stats": {"total": 0, "error": 0, "warning": 0, "info": 0, "ignore": 0}}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    # Zähle Errors/Warnings/Info/Ignore in ALLEN Zeilen
    stats = {"total": len(all_lines), "error": 0, "warning": 0, "info": 0, "ignore": 0}
    for line in all_lines:
        if is_expected_yfinance_error(line):
            stats["ignore"] += 1
        elif "[ERROR]" in line:
            stats["error"] += 1
        elif "[WARNING]" in line:
            stats["warning"] += 1
        elif "[INFO]" in line:
            stats["info"] += 1
    
    result_lines = all_lines[-lines:]
    
    # Level-Filter anwenden
    if level:
        level_upper = level.upper()
        if level_upper == "IGNORE":
            result_lines = [l for l in result_lines if is_expected_yfinance_error(l)]
        else:
            level_tag = f"[{level_upper}]"
            result_lines = [l for l in result_lines if level_tag in l and not is_expected_yfinance_error(l)]
    
    return {"logs": result_lines, "stats": stats}

@app.get("/api/logs/stats")
async def get_log_stats():
    """Gibt Statistiken über Log-Level-Verteilung zurück (Error/Warning/Info Counts)."""
    from backend.app.logger import LOG_FILE, is_expected_yfinance_error
    if not os.path.exists(LOG_FILE): return {"stats": {"total": 0, "error": 0, "warning": 0, "info": 0, "ignore": 0}, "recent_errors": []}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    
    stats = {"total": len(all_lines), "error": 0, "warning": 0, "info": 0, "ignore": 0}
    recent_errors = []
    recent_warnings = []
    
    for line in all_lines:
        if is_expected_yfinance_error(line):
            stats["ignore"] += 1
        elif "[ERROR]" in line:
            stats["error"] += 1
            recent_errors.append(line.strip())
        elif "[WARNING]" in line:
            stats["warning"] += 1
            recent_warnings.append(line.strip())
        elif "[INFO]" in line:
            stats["info"] += 1
    
    return {
        "stats": stats,
        "recent_errors": recent_errors[-20:],
        "recent_warnings": recent_warnings[-20:],
    }

@app.get("/api/logs/export")
async def export_logs():
    from backend.app.logger import LOG_FILE
    from backend.app.utils.timezone import now_mez
    if not os.path.exists(LOG_FILE): return {"error": "No log file"}
    filename = f"kafin_logs_{now_mez().strftime('%Y%m%d_%H%M%S')}.log"
    return FileResponse(LOG_FILE, media_type="text/plain", filename=filename)

@app.delete("/api/logs/file")
async def clear_logs():
    from backend.app.logger import LOG_FILE, _log_buffer
    _log_buffer.clear()
    try:
        with open(LOG_FILE, "r+", encoding="utf-8") as f:
            f.truncate(0)
    except Exception as e:
        logger.error(f"Clear Logs Error: {e}")
    return {"status": "cleared"}

class ExternalLog(BaseModel):
    level: str
    message: str
    source: str = "n8n"
    error_code: str | None = None

@app.post("/api/logs/external")
async def receive_external_log(log: ExternalLog):
    """Webhook für n8n und externe Services zum Pushen von Logs"""
    from backend.app.logger import get_logger
    logger_ext = get_logger(log.source)
    msg = f"[EXTERNAL] {log.message}"
    if log.error_code: msg += f" | CODE: {log.error_code}"
    
    if log.level.lower() == "error": logger_ext.error(msg)
    elif log.level.lower() == "warning": logger_ext.warning(msg)
    else: logger_ext.info(msg)
    return {"status": "logged"}

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
            data = await db.table(table).select("*", count="exact").limit(0).execute_async()
            results[table] = {"count": data.count if hasattr(data, "count") else "unknown", "status": "ok"}
        except Exception as e:
            results[table] = {"count": 0, "status": f"error: {str(e)[:100]}"}

    return {"status": "success", "tables": results}

@app.get("/api/diagnostics/full", tags=["System"])
async def full_system_diagnostics():
    import asyncio, time
    from datetime import datetime, timedelta
    from backend.app.db import get_supabase_client
    from backend.app.data.finnhub import get_company_news
    from backend.app.data.fmp import get_company_profile as fmp_profile
    from backend.app.data.fred import get_macro_snapshot
    from backend.app.analysis.deepseek import call_deepseek
    from backend.app.analysis.finbert import analyze_sentiment
    from backend.app.logger import get_logger
    
    logger = get_logger(__name__)
    logger.info("=== Starting Full System Diagnostics ===")
    
    results = {"status": "ok", "timestamp": datetime.utcnow().isoformat(), "services": {}}
    
    async def measure(func, *args):
        t0 = time.time()
        try:
            res = await func(*args) if args else await func()
            return res, round((time.time() - t0) * 1000)
        except Exception as e:
            logger.error(f"Error measuring {func.__name__}: {e}")
            raise

    # 1. Supabase
    logger.info("🔍 Testing Supabase connection...")
    try:
        t0 = time.time()
        db = get_supabase_client()
        wl = await db.table("watchlist").select("ticker").limit(1).execute_async() if db else None
        ms = round((time.time() - t0) * 1000)
        results["services"]["supabase"] = {"status": "ok" if wl else "error", "latency_ms": ms, "details": "DB connected"}
        logger.info(f"✅ Supabase: OK ({ms}ms)")
    except Exception as e:
        results["services"]["supabase"] = {"status": "error", "error_code": "DB_CONN_ERR", "details": str(e)}
        logger.error(f"❌ Supabase: ERROR - {e}")

    # 2. Finnhub API
    logger.info("🔍 Testing Finnhub API...")
    try:
        from backend.app.utils.timezone import now_mez
        now = now_mez()
        from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")
        res, ms = await measure(get_company_news, "AAPL", from_date, to_date)
        results["services"]["finnhub"] = {"status": "ok" if res else "warning", "latency_ms": ms, "details": "API responsive"}
        logger.info(f"✅ Finnhub: OK ({ms}ms, {len(res) if res else 0} items)")
    except Exception as e:
        results["services"]["finnhub"] = {"status": "error", "error_code": "FINNHUB_API_ERR", "details": repr(e)}
        logger.error(f"❌ Finnhub: ERROR - {e}")

    # 3. FMP API
    logger.info("🔍 Testing FMP API...")
    try:
        res, ms = await measure(fmp_profile, "AAPL")
        results["services"]["fmp"] = {"status": "ok" if res else "warning", "latency_ms": ms, "details": "API responsive"}
        logger.info(f"✅ FMP: OK ({ms}ms)")
    except Exception as e:
        results["services"]["fmp"] = {"status": "error", "error_code": "FMP_API_ERR", "details": repr(e)}
        logger.error(f"❌ FMP: ERROR - {e}")

    # 4. FRED API
    logger.info("🔍 Testing FRED API...")
    try:
        res, ms = await measure(get_macro_snapshot)
        results["services"]["fred"] = {"status": "ok" if res else "warning", "latency_ms": ms, "details": "API responsive"}
        logger.info(f"✅ FRED: OK ({ms}ms)")
    except Exception as e:
        results["services"]["fred"] = {"status": "error", "error_code": "FRED_API_ERR", "details": repr(e)}
        logger.error(f"❌ FRED: ERROR - {e}")

    # 5. AI Services
    logger.info("🔍 Testing DeepSeek API...")
    try:
        res, ms = await measure(call_deepseek, "Reply OK", "Test")
        results["services"]["deepseek"] = {"status": "ok", "latency_ms": ms, "details": "LLM responsive"}
        logger.info(f"✅ DeepSeek: OK ({ms}ms)")
    except Exception as e:
        results["services"]["deepseek"] = {"status": "error", "error_code": "DEEPSEEK_ERR", "details": repr(e)}
        logger.error(f"❌ DeepSeek: ERROR - {e}")
        
    logger.info("🔍 Testing FinBERT model...")
    try:
        t0 = time.time()
        await asyncio.to_thread(analyze_sentiment, "Test sentence.")
        ms = round((time.time() - t0) * 1000)
        results["services"]["finbert"] = {"status": "ok", "latency_ms": ms, "details": "Model loaded"}
        logger.info(f"✅ FinBERT: OK ({ms}ms)")
    except Exception as e:
        results["services"]["finbert"] = {"status": "error", "error_code": "FINBERT_ERR", "details": repr(e)}
        logger.error(f"❌ FinBERT: ERROR - {e}")

    # 6. Telegram
    logger.info("🔍 Testing Telegram connection...")
    try:
        from backend.app.alerts.telegram import send_telegram_alert
        await send_telegram_alert("🧪 Systemcheck: Alle APIs getestet.")
        results["services"]["telegram"] = {"status": "ok", "details": "Notification sent"}
        logger.info("✅ Telegram: OK")
    except Exception as e:
        results["services"]["telegram"] = {"status": "error", "error_code": "TELEGRAM_ERR", "details": repr(e)}
        logger.error(f"❌ Telegram: ERROR - {e}")

    # 7. n8n
    logger.info("🔍 Testing n8n connection...")
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get("http://kafin-n8n:5678/healthz", timeout=5.0)
            results["services"]["n8n"] = {"status": "ok" if response.status_code == 200 else "warning", "details": f"Status {response.status_code}"}
            logger.info(f"✅ n8n: OK (status {response.status_code})")
    except Exception as e:
        results["services"]["n8n"] = {"status": "error", "error_code": "N8N_ERR", "details": repr(e)}
        logger.error(f"❌ n8n: ERROR - {e}")

    if any(s.get("status") == "error" for s in results["services"].values()):
        results["status"] = "degraded"
        logger.warning("⚠️ System status: DEGRADED")
    else:
        logger.info("✅ System status: OK")
    
    logger.info("=== Full System Diagnostics Complete ===")
    return results

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

