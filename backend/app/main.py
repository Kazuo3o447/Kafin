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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.logger import get_logger, get_recent_logs, get_module_status
from backend.app.admin import router as admin_router
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
from backend.app.cache import cache_get, cache_set
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
    logger.info("Phase-4A Tabellen SQL — bitte in Supabase ausführen:")
    logger.info("\n" + get_schema_extension_sql())
    log_custom_search_terms_sql()
    logger.info("API Call: admin init tables SQL ausgegeben")
    return {"status": "success", "sql": sql}

@app.get("/api/logs")
async def api_get_logs(level: str = None, limit: int = 200):
    """Gibt die letzten Log-Einträge zurück."""
    logs = get_recent_logs()
    if level:
        logs = [l for l in logs if l.get("level") == level]
    return {"logs": logs[:limit]}

@app.get("/api/logs/errors")
async def api_get_logs_errors():
    """Gibt nur Log-Einträge mit level 'error' oder 'warning' der letzten 24 Stunden zurück, maximal 50."""
    logs = get_recent_logs()
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)
    
    errors = []
    for log in logs:
        level = log.get("level", "").lower()
        if level in ("error", "warning", "critical"):
            try:
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
        reviews_res = (
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
            .execute()
        )
        reviews = reviews_res.data or []
    except Exception as exc:
        logger.error(f"Track Record: earnings_reviews Fehler für {normalized_ticker}: {exc}")
        return base_response

    try:
        audits_res = (
            db.table("audit_reports")
            .select("id,ticker,report_date,earnings_date,opportunity_score,torpedo_score,recommendation,created_at")
            .eq("ticker", normalized_ticker)
            .order("report_date", desc=True)
            .limit(8)
            .execute()
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


@data_router.get("/score-delta/{ticker}")
async def api_score_delta(ticker: str):
    """Gibt aktuelle Scores und deren Veränderung vs. gestern/letzte Woche zurück."""
    logger.info(f"API Call: score-delta for {ticker}")
    db = get_supabase_client()
    if not db:
        return {"error": "Supabase nicht verfügbar"}

    try:
        result = (
            db.table("score_history")
            .select("*")
            .eq("ticker", ticker)
            .order("date", desc=True)
            .limit(7)
            .execute()
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


@data_router.get("/earnings-radar")
async def api_earnings_radar(days: int = 14):
    from datetime import datetime, timedelta
    from backend.app.data.finnhub import get_earnings_calendar
    from backend.app.memory.watchlist import get_watchlist

    cache_key = f"earnings_radar_{days}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    now = datetime.now()
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
        result = query.limit(100).execute()
        data = result.data or []
        return {"trades": data, "count": len(data)}
    except Exception as exc:  # noqa: BLE001
        return {"trades": [], "count": 0, "error": str(exc)}


@app.get("/api/shadow-portfolio/weekly-report")
async def api_shadow_portfolio_weekly():
    report = await get_weekly_shadow_report()
    return {"report": report}


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
        reviews = (
            supabase.table("earnings_reviews")
            .select(
                "quarter,pre_earnings_report_date,pre_earnings_recommendation,"
                "actual_surprise_percent,stock_reaction_1d_percent"
            )
            .eq("ticker", ticker)
            .order("created_at", desc=True)
            .limit(12)
            .execute()
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
        audits = (
            supabase.table("audit_reports")
            .select("report_date,earnings_date,opportunity_score,torpedo_score,recommendation")
            .eq("ticker", ticker)
            .order("report_date", desc=True)
            .limit(8)
            .execute()
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
        torpedo_rows = (
            supabase.table("short_term_memory")
            .select("date,bullet_points,sentiment_score,is_material")
            .eq("ticker", ticker)
            .eq("is_material", True)
            .order("date", desc=True)
            .limit(20)
            .execute()
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
        narrative_rows = (
            supabase.table("short_term_memory")
            .select("date,shift_type,shift_reasoning,bullet_points,sentiment_score,is_narrative_shift")
            .eq("ticker", ticker)
            .eq("is_narrative_shift", True)
            .order("date", desc=True)
            .limit(15)
            .execute()
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

@watchlist_router.get("")
async def api_get_watchlist():
    logger.info("API Call: get-watchlist")
    return await get_watchlist()


def _fetch_ticker_data_sync(ticker: str, entry: dict) -> dict:
    """
    Synchrone Hilfsfunktion für yfinance-Calls.
    Wird via asyncio.to_thread() im Thread-Pool ausgeführt.
    """
    import yfinance as yf
    from datetime import datetime as dt

    stock = yf.Ticker(ticker)

    # --- Kursdaten via fast_info (10x schneller als stock.info) ---
    try:
        fi = stock.fast_info
        # Preis — separater Try-Block
        try:
            if fi.last_price:
                entry["price"] = round(float(fi.last_price), 2)
        except Exception:
            pass
        # Change % — separater Try-Block
        try:
            val = fi.regular_market_day_change_percent
            if val is not None:
                entry["change_pct"] = round(float(val) * 100, 2)
        except Exception:
            pass
        # Market Cap — separater Try-Block
        try:
            if fi.market_cap:
                entry["market_cap_b"] = round(float(fi.market_cap) / 1e9, 1)
        except Exception:
            pass
    except Exception:
        pass

    # Fallback für Preis wenn fast_info komplett fehlschlägt
    if not entry.get("price"):
        try:
            hist = stock.history(period="2d")
            if not hist.empty:
                entry["price"] = round(float(hist["Close"].iloc[-1]), 2)
                if len(hist) >= 2:
                    prev = float(hist["Close"].iloc[-2])
                    curr = float(hist["Close"].iloc[-1])
                    if prev:
                        entry["change_pct"] = round(((curr - prev) / prev) * 100, 2)
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
                    entry["earnings_date"] = str(earnings_date)
                    entry["earnings_countdown"] = days_until
    except Exception:
        pass

    return entry


def _fetch_all_scores_sync(tickers: list, db) -> dict:
    """
    Lädt score_history für alle Ticker in EINER einzigen Supabase-Query.
    Gibt ein Dict zurück: {ticker: [latest_row, prev_row]}
    """
    if not db or not tickers:
        return {}
    try:
        res = (
            db.table("score_history")
            .select("*")
            .in_("ticker", tickers)
            .order("date", desc=True)
            .execute()
        )
        rows = res.data if res and res.data else []

        # Gruppiere nach Ticker, behalte die 2 neuesten pro Ticker
        by_ticker: dict = {}
        for row in rows:
            t = row.get("ticker", "").upper()
            if t not in by_ticker:
                by_ticker[t] = []
            if len(by_ticker[t]) < 2:
                by_ticker[t].append(row)

        return by_ticker
    except Exception as e:
        logger.debug(f"Batch score fetch error: {e}")
        return {}


async def _enrich_single(item: dict, scores_by_ticker: dict) -> dict:
    """
    Enriched einen einzelnen Watchlist-Ticker mit Kursdaten + Scores.
    Wird parallel via asyncio.gather aufgerufen.
    """
    ticker = item.get("ticker")
    if not ticker:
        return item

    entry = dict(item)

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
    except Exception as exc:
        logger.debug(f"Enrich scores {ticker}: {exc}")

    return entry


@watchlist_router.get("/enriched")
async def api_watchlist_enriched():
    """Gibt Watchlist inkl. Kurse, Scores und Earnings-Countdown zurück."""
    logger.info("API Call: watchlist-enriched")

    watchlist = await get_watchlist()
    db = get_supabase_client()

    # Einmalige Batch-Query für alle Scores
    tickers = [item.get("ticker", "") for item in watchlist if item.get("ticker")]
    scores_by_ticker = await asyncio.to_thread(_fetch_all_scores_sync, tickers, db)

    # ALLE Ticker parallel enrichen mit vorgeladenen Scores
    results = await asyncio.gather(
        *[_enrich_single(item, scores_by_ticker) for item in watchlist],
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

    return {
        "watchlist": enriched,
        "concentration_warning": concentration_warning,
        "sector_distribution": sectors,
    }

@watchlist_router.post("")
async def api_add_watchlist_item(item: WatchlistItemCreate):
    logger.info(f"API Call: add-watchlist-item {item.ticker}")
    # Wenn kein Firmenname: Ticker als Name verwenden
    company_name = item.company_name or item.ticker.upper()
    sector = item.sector or "Unknown"
    return await add_ticker(
        item.ticker, company_name, sector,
        item.notes or "", item.cross_signals or []
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

app.include_router(admin_router)
app.include_router(data_router)
app.include_router(google_news_router)
app.include_router(reports_router)
app.include_router(watchlist_router)   # <-- DIESER EINE ZEILE

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

