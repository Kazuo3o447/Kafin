from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Any
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import asyncio
from types import SimpleNamespace

from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set
from backend.app.db import get_supabase_client
from backend.app.data.finnhub import (
    get_earnings_calendar, get_company_news, get_short_interest, get_insider_transactions
)
from backend.app.data.fmp import (
    get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics,
    get_price_target_consensus, get_analyst_grades
)
from backend.app.data.fred import get_macro_snapshot
from backend.app.data.yfinance_data import (
    get_risk_metrics, get_atm_implied_volatility, get_historical_volatility,
    get_technical_setup, get_fundamentals_yf, get_options_metrics, get_options_oi_analysis,
    get_earnings_history_yf, get_short_interest_yf, get_vwap
)
from backend.app.data.ticker_resolver import resolve_ticker
from backend.app.data.finra import get_finra_short_volume
from backend.app.data.reddit_monitor import get_reddit_sentiment
from backend.app.data.fear_greed import get_fear_greed_score
from backend.app.data.market_overview import get_market_overview, get_market_news_for_sentiment, get_market_breadth, get_intermarket_signals
from backend.app.memory.long_term import get_insights
from backend.app.memory.short_term import get_bullet_points, _calc_sentiment_from_bullets, get_bullet_points_batch
from backend.app.memory.watchlist import get_watchlist
from backend.app.utils.timezone import now_mez
from backend.app.utils.constants import SECTOR_TO_ETF

from schemas.earnings import EarningsExpectation, EarningsHistorySummary
from schemas.sentiment import NewsBulletPoint, ShortInterestData, InsiderActivity
from schemas.valuation import ValuationData
from schemas.macro import MacroSnapshot
from schemas.options import OptionsData

logger = get_logger(__name__)
router = APIRouter(prefix="/api/data", tags=["data"])

@router.get("/earnings-calendar", response_model=List[EarningsExpectation])
async def api_earnings_calendar(from_date: str, to_date: str):
    logger.info(f"API Call: earnings-calendar {from_date} to {to_date}")
    return await get_earnings_calendar(from_date, to_date)

@router.get("/company/{ticker}/news", response_model=List[NewsBulletPoint])
async def api_company_news(ticker: str, from_date: str = "2026-01-01", to_date: str = "2026-12-31"):
    logger.info(f"API Call: company-news for {ticker}")
    return await get_company_news(ticker, from_date, to_date)

@router.get("/company/{ticker}/short-interest", response_model=ShortInterestData)
async def api_short_interest(ticker: str):
    logger.info(f"API Call: short-interest for {ticker}")
    return await get_short_interest(ticker)

@router.get("/company/{ticker}/insiders", response_model=InsiderActivity)
async def api_insiders(ticker: str):
    logger.info(f"API Call: insiders for {ticker}")
    return await get_insider_transactions(ticker)

@router.get("/company/{ticker}/profile", response_model=ValuationData)
async def api_profile(ticker: str):
    logger.info(f"API Call: profile for {ticker}")
    return await get_company_profile(ticker)

@router.get("/company/{ticker}/estimates", response_model=EarningsExpectation)
async def api_estimates(ticker: str):
    logger.info(f"API Call: estimates for {ticker}")
    return await get_analyst_estimates(ticker)

@router.get("/company/{ticker}/earnings-history", response_model=EarningsHistorySummary)
async def api_earnings_history(ticker: str):
    logger.info(f"API Call: earnings-history for {ticker}")
    return await get_earnings_history(ticker)

@router.get("/macro", response_model=MacroSnapshot)
async def api_macro():
    logger.info(f"API Call: macro snapshot")
    return await get_macro_snapshot()

@router.get("/long-term-memory/{ticker}")
async def api_long_term_memory(ticker: str):
    """Gibt das Langzeit-Gedächtnis für einen Ticker zurück."""
    insights = await get_insights(ticker)
    return {"ticker": ticker, "count": len(insights), "insights": insights}

@router.get("/ticker-track-record/{ticker}")
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
        torp_score = _to_float(review.get("pre_earnings_score_torpedo"))
        reaction = _to_float(review.get("stock_reaction_1d_percent"))
        if torp_score is None or reaction is None:
            continue
        if torp_score >= 6.0:
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

@router.get("/performance")
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

@router.get("/options/{ticker}", response_model=OptionsData)
async def api_options_data(ticker: str):
    """Holt Options-Daten inkl. IV ATM, Put/Call Ratio, historischer Volatilität."""
    logger.info(f"API Call: options-data for {ticker}")
    options_data = await get_atm_implied_volatility(ticker)
    if options_data is None:
        return OptionsData(ticker=ticker)
    return options_data

@router.get("/risk-metrics/{ticker}")
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

@router.get("/score-delta/{ticker}")
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

@router.get("/sparkline/{ticker}")
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

@router.get("/quick-snapshot/{ticker}")
async def api_quick_snapshot(ticker: str):
    ticker = ticker.upper().strip()
    cache_key = f"quick_snapshot_{ticker}"
    cached = cache_get(cache_key)
    if cached:
        return cached

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

        latest_audit = None
        try:
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

@router.get("/volume-profile/{ticker}")
async def api_volume_profile(ticker: str):
    """Holt 20-Tage Volumen-Profil für Visualisierung."""
    ticker = ticker.upper().strip()
    try:
        def _fetch_volume_data():
            stock = yf.Ticker(ticker)
            hist = stock.history(period="25d")
            if hist.empty or len(hist) < 2:
                return []
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
            return result[-20:]
        
        data = await asyncio.to_thread(_fetch_volume_data)
        avg_volume = sum(d["volume"] for d in data) / len(data) if data else 0
        return {"ticker": ticker, "data": data, "avg_volume": int(avg_volume)}
    except Exception as e:
        logger.error(f"Volume Profile Fehler für {ticker}: {e}")
        return {"ticker": ticker, "data": [], "avg_volume": 0}

@router.get("/research/{ticker}")
async def api_research_dashboard(
    ticker: str,
    force_refresh: bool = False,
    override_ticker: Optional[str] = None,
):
    """Aggregierter Research-Endpoint für das Trading-Dashboard."""
    ticker = ticker.upper().strip()
    cache_key = f"research_dashboard_{ticker}"

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
        get_market_overview(),                           # 13
        get_analyst_grades(effective_ticker),           # 14
        get_market_news_for_sentiment(),                 # 15
        get_options_oi_analysis(effective_ticker),       # 16
        get_finra_short_volume(effective_ticker),        # 17
        get_reddit_sentiment(effective_ticker),          # 18
        get_fear_greed_score(),                          # 19
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

    if (not history or not getattr(history, "all_quarters", None)):
        yf_history = await get_earnings_history_yf(effective_ticker)
        if yf_history:
            history = SimpleNamespace(
                quarters_beat=yf_history["quarters_beat"],
                avg_surprise_percent=yf_history["avg_surprise_percent"],
                all_quarters=yf_history["all_quarters"],
                last_quarter=SimpleNamespace(**yf_history["all_quarters"][0]) if yf_history["all_quarters"] else None,
                source="yfinance",
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

    is_watchlist = any(w.get("ticker", "").upper() == ticker for w in (watchlist if isinstance(watchlist, list) else []))
    watchlist_item = next((w for w in watchlist if w.get("ticker", "").upper() == ticker), None)

    price = None
    change_pct = None
    try:
        if tech and not isinstance(tech, Exception):
            price = getattr(tech, "current_price", None)
            change_pct = getattr(tech, "change_1d_pct", None)
    except Exception: pass

    if price is None and isinstance(yf_fund, dict):
        price = yf_fund.get("price")
        if change_pct is None: change_pct = yf_fund.get("change_pct")

    pre_market_price = post_market_price = pre_market_change = None
    try:
        def _fetch_extended():
            fi = yf.Ticker(effective_ticker).fast_info
            pre, post, reg = getattr(fi, "pre_market_price", None), getattr(fi, "post_market_price", None), getattr(fi, "last_price", None)
            return (round(float(pre), 2) if pre else None, round(float(post), 2) if post else None, round(float(reg), 2) if reg else None)
        pre_p, post_p, reg_p = await asyncio.to_thread(_fetch_extended)
        pre_market_price, post_market_price = pre_p, post_p
        if pre_p and reg_p and reg_p > 0: pre_market_change = round((pre_p - reg_p) / reg_p * 100, 2)
        elif post_p and reg_p and reg_p > 0: pre_market_change = round((post_p - reg_p) / reg_p * 100, 2)
    except Exception: pass

    if price is None:
        try:
            def _fetch_price_fallback():
                fi = yf.Ticker(effective_ticker).fast_info
                p, c = getattr(fi, "last_price", None), getattr(fi, "regular_market_day_change_percent", None)
                return (round(float(p), 2) if p is not None else None, round(float(c) * 100, 2) if c is not None else None)
            price, change_pct = await asyncio.to_thread(_fetch_price_fallback)
        except Exception: pass

    pe_ratio = forward_pe = ps_ratio = peg_ratio = ev_ebitda = debt_equity = fcf_yield = current_ratio = market_cap = beta = dividend_yield = revenue_ttm = eps_ttm = sector = industry = company_name = fifty_two_week_high = fifty_two_week_low = analyst_target = analyst_recommendation = number_of_analysts = None

    if metrics:
        pe_ratio, ps_ratio, market_cap, debt_equity, fcf_yield, current_ratio, sector, industry = getattr(metrics, "pe_ratio", None), getattr(metrics, "ps_ratio", None), getattr(metrics, "market_cap", None), getattr(metrics, "debt_to_equity", None), getattr(metrics, "free_cash_flow_yield", None), getattr(metrics, "current_ratio", None), getattr(metrics, "sector", None), getattr(metrics, "industry", None)

    if yf_fund:
        pe_ratio, forward_pe, ps_ratio, market_cap, beta, dividend_yield, revenue_ttm, eps_ttm, sector, industry, fifty_two_week_high, fifty_two_week_low, analyst_target, analyst_recommendation, number_of_analysts = pe_ratio or yf_fund.get("pe_ratio"), yf_fund.get("forward_pe"), ps_ratio or yf_fund.get("ps_ratio"), market_cap or yf_fund.get("market_cap"), yf_fund.get("beta"), yf_fund.get("dividend_yield"), yf_fund.get("revenue_ttm"), yf_fund.get("eps_ttm"), sector or yf_fund.get("sector"), industry or yf_fund.get("industry"), yf_fund.get("fifty_two_week_high"), yf_fund.get("fifty_two_week_low"), yf_fund.get("analyst_target"), yf_fund.get("analyst_recommendation"), yf_fund.get("number_of_analysts")

    ceo = employees = description = website = ipo_date = country = exchange = None
    peers_list = []
    if profile:
        company_name, sector, industry, ceo, employees, description, website, ipo_date, country, exchange = getattr(profile, "company_name", None), sector or getattr(profile, "sector", None), industry or getattr(profile, "industry", None), getattr(profile, "ceo", None), getattr(profile, "fullTimeEmployees", None) or getattr(profile, "employees", None), getattr(profile, "description", None), getattr(profile, "website", None), getattr(profile, "ipoDate", None) or getattr(profile, "ipo_date", None), getattr(profile, "country", None), getattr(profile, "exchange", None)
        try:
            raw_peers = getattr(profile, "peers", None)
            if isinstance(raw_peers, list): peers_list = [str(p).upper() for p in raw_peers[:5]]
        except Exception: pass

    sector_earnings = []
    try:
        sector_norm = str(sector or "").strip().lower()
        if sector_norm:
            today = date.today()
            in_14 = today + timedelta(days=14)
            cal = await get_earnings_calendar(from_date=today.isoformat(), to_date=in_14.isoformat())
            if cal:
                cal_by_ticker = { (getattr(item, "ticker", None) or getattr(item, "symbol", None) or "").upper(): item for item in (cal if isinstance(cal, list) else []) if (getattr(item, "ticker", None) or getattr(item, "symbol", None) or "").upper() }
                for w in (watchlist if isinstance(watchlist, list) else []):
                    item_ticker = str(w.get("ticker", "")).upper()
                    if not item_ticker or item_ticker == ticker.upper(): continue
                    if str(w.get("sector", "")).strip().lower() != sector_norm: continue
                    cal_item = cal_by_ticker.get(item_ticker)
                    if cal_item: sector_earnings.append({"ticker": item_ticker, "date": getattr(cal_item, "report_date", None), "timing": getattr(cal_item, "report_timing", None) or getattr(cal_item, "hour", None)})
    except Exception as e: logger.debug(f"Sektor-Kalender Fehler: {e}")

    roe = roa = None
    try:
        from backend.app.data.fmp import _fmp_get
        raw_metrics = await _fmp_get("/stable/key-metrics-ttm", {"symbol": ticker})
        if raw_metrics and isinstance(raw_metrics, list) and raw_metrics:
            raw = raw_metrics[0]
            peg_ratio, ev_ebitda, roe, roa = raw.get("priceEarningsToGrowthRatioTTM") or raw.get("pegRatioTTM"), raw.get("enterpriseValueOverEBITDATTM") or raw.get("evToEbitdaTTM"), raw.get("returnOnEquityTTM"), raw.get("returnOnAssetsTTM")
    except Exception: pass

    expected_move_pct = expected_move_usd = None
    try:
        import math
        iv = getattr(options, "implied_volatility_atm", None) if options else None
        earnings_dt = getattr(estimates, "report_date", None) if estimates else None
        days_to_earnings = 1
        if earnings_dt:
            try:
                if hasattr(earnings_dt, "toordinal"): days_to_earnings = max(1, (earnings_dt - _date.today()).days)
                else: days_to_earnings = max(1, (datetime.fromisoformat(str(earnings_dt)).date() - date.today()).days)
            except Exception: days_to_earnings = 1
        if iv is not None and iv > 0 and price is not None and price > 0:
            expected_move_pct = round(iv * math.sqrt(days_to_earnings / 365) * 100, 1)
            expected_move_usd = round(price * iv * math.sqrt(days_to_earnings / 365), 2)
    except Exception: pass

    earnings_date = report_timing = eps_consensus = revenue_consensus = beats_of_8 = avg_surprise = last_surprise_pct = last_beat = None
    quarterly_history = []
    if estimates:
        earnings_date, report_timing, eps_consensus, revenue_consensus = str(getattr(estimates, "report_date", None) or ""), getattr(estimates, "report_timing", None), getattr(estimates, "eps_consensus", None), getattr(estimates, "revenue_consensus", None)
    if history:
        beats_of_8, avg_surprise = getattr(history, "quarters_beat", None), getattr(history, "avg_surprise_percent", None)
        last_q = getattr(history, "last_quarter", None)
        if last_q:
            last_surprise_pct = float(getattr(last_q, "eps_surprise_percent", None)) if getattr(last_q, "eps_surprise_percent", None) is not None else None
            last_beat = bool((last_surprise_pct or 0) > 0)
        for q in getattr(history, "all_quarters", [])[:8]:
            quarterly_history.append({
                "quarter": q.get("quarter", ""),
                "eps_actual": float(q.get("eps_actual")) if q.get("eps_actual") is not None else None,
                "eps_consensus": float(q.get("eps_consensus")) if q.get("eps_consensus") is not None else None,
                "surprise_pct": float(q.get("eps_surprise_percent")) if q.get("eps_surprise_percent") is not None else None,
                "reaction_1d": float(q.get("stock_reaction_1d")) if q.get("stock_reaction_1d") is not None else None
            })

    earnings_countdown = None
    earnings_today = False
    if earnings_date:
        try:
            ed = datetime.fromisoformat(earnings_date).date()
            earnings_countdown = (ed - date.today()).days
            earnings_today = earnings_countdown == 0
        except Exception: pass

    price_change_30d = None
    try:
        if tech and not isinstance(tech, Exception):
            price_change_30d = getattr(tech, "change_1m_pct", None)
            if price_change_30d is None: price_change_30d = yf_fund.get("change_1m_pct") if isinstance(yf_fund, dict) else None
    except Exception: pass

    market_ov = market_ov or {}
    indices_data = market_ov.get("indices", {})
    spy_data = indices_data.get("SPY", {})
    sector_etf_symbol = SECTOR_TO_ETF.get(sector or "", None)
    sector_etf_full = indices_data.get(sector_etf_symbol, {})
    price_change_5d = None
    try:
        if tech and not isinstance(tech, Exception):
            price_change_5d = getattr(tech, "change_5d_pct", None)
            if price_change_5d is None: price_change_5d = yf_fund.get("change_5d_pct") if isinstance(yf_fund, dict) else None
    except Exception: pass

    def rel_str(t_pct, b_pct): return round(t_pct - b_pct, 2) if t_pct is not None and b_pct is not None else None
    rel_strength = {"vs_spy_1d": rel_str(change_pct, spy_data.get("change_1d_pct")), "vs_spy_5d": rel_str(price_change_5d, spy_data.get("change_5d_pct")), "vs_spy_1m": rel_str(price_change_30d, spy_data.get("change_1m_pct")), "vs_sector_1d": rel_str(change_pct, sector_etf_full.get("change_1d_pct")), "vs_sector_5d": rel_str(price_change_5d, sector_etf_full.get("change_5d_pct")), "vs_sector_1m": rel_str(price_change_30d, sector_etf_full.get("change_1m_pct")), "spy_1d": spy_data.get("change_1d_pct"), "spy_5d": spy_data.get("change_5d_pct"), "spy_1m": spy_data.get("change_1m_pct"), "sector_etf": sector_etf_symbol, "sector_1d": sector_etf_full.get("change_1d_pct"), "sector_5d": sector_etf_full.get("change_5d_pct"), "sector_1m": sector_etf_full.get("change_1m_pct")}
    outperf_count = sum(1 for v in [rel_strength["vs_spy_1d"], rel_strength["vs_spy_5d"], rel_strength["vs_sector_5d"]] if v is not None and v > 0)
    rel_strength["label"] = "Stark outperformend" if outperf_count >= 3 else "Leicht outperformend" if outperf_count >= 2 else "Leicht underperformend" if outperf_count == 1 else "Underperformend"
    rel_strength["signal"] = "bullish" if outperf_count >= 3 else "bearish" if outperf_count == 0 else "neutral"

    short_interest_pct = days_to_cover = squeeze_risk = None
    if short_int: short_interest_pct, days_to_cover, squeeze_risk = getattr(short_int, "short_interest_percent", None), getattr(short_int, "days_to_cover", None), getattr(short_int, "squeeze_risk", None)
    if not short_interest_pct:
        try:
            yf_si = await get_short_interest_yf(effective_ticker)
            if yf_si: short_interest_pct, days_to_cover = yf_si.get("short_interest_percent"), yf_si.get("short_ratio") or days_to_cover
        except Exception: pass

    insider_buys = insider_sells = insider_buy_value = insider_sell_value = 0.0
    insider_assessment = "normal"
    if insiders: insider_buys, insider_sells, insider_buy_value, insider_sell_value, insider_assessment = getattr(insiders, "total_buys", 0) or 0, getattr(insiders, "total_sells", 0) or 0, getattr(insiders, "total_buy_value", 0.0) or 0.0, getattr(insiders, "total_sell_value", 0.0) or 0.0, getattr(insiders, "assessment", "normal") or "normal"

    news_bullets = []
    for b in (news_mem or [])[:8]: news_bullets.append({"text": b.get("bullet_text", "") or b.get("insight", ""), "sentiment": b.get("sentiment_score", 0), "is_material": b.get("is_material", False), "category": b.get("category", "News"), "date": b.get("date", "") or b.get("created_at", ""), "source": "finbert"})
    if len(news_bullets) < 5 and news_items:
        for item in (news_items or [])[:8]:
            headline = item.get("headline", "") if isinstance(item, dict) else ""
            if not headline: continue
            published = item.get("datetime", 0)
            news_bullets.append({"text": headline, "sentiment": 0, "is_material": False, "category": item.get("category", "News"), "date": datetime.fromtimestamp(published).strftime("%Y-%m-%d") if published else "", "source": "finnhub", "url": item.get("url", "")})

    price_target_high = price_target_low = price_target_avg = None
    if price_tgt: price_target_high, price_target_low, price_target_avg = price_tgt.get("targetHigh") or price_tgt.get("targetHighPrice"), price_tgt.get("targetLow") or price_tgt.get("targetLowPrice"), price_tgt.get("targetConsensus") or price_tgt.get("targetMeanPrice")
    if not price_target_avg and analyst_target: price_target_avg = analyst_target

    rsi = trend = sma_50 = sma_200 = above_sma50 = above_sma200 = sma50_distance = sma200_distance = support = resistance = distance_52w_high = sma_20 = atr_14 = macd = macd_signal_val = macd_histogram = macd_bullish = obv = obv_trend = rvol = float_shares = avg_volume = bid_ask_spread = None
    if tech: rsi, trend, sma_50, sma_200, above_sma50, above_sma200, sma50_distance, sma200_distance, support, resistance, distance_52w_high, sma_20, atr_14, macd, macd_signal_val, macd_histogram, macd_bullish, obv, obv_trend, rvol, float_shares, avg_volume, bid_ask_spread = getattr(tech, "rsi_14", None), getattr(tech, "trend", None), getattr(tech, "sma_50", None), getattr(tech, "sma_200", None), getattr(tech, "above_sma50", None), getattr(tech, "above_sma200", None), getattr(tech, "sma50_distance_pct", None), getattr(tech, "sma200_distance_pct", None), getattr(tech, "support_level", None), getattr(tech, "resistance_level", None), getattr(tech, "distance_to_52w_high_percent", None), getattr(tech, "sma_20", None), getattr(tech, "atr_14", None), getattr(tech, "macd", None), getattr(tech, "macd_signal", None), getattr(tech, "macd_histogram", None), getattr(tech, "macd_bullish", None), getattr(tech, "obv", None), getattr(tech, "obv_trend", None), getattr(tech, "rvol", None), getattr(tech, "float_shares", None), getattr(tech, "avg_volume", None), getattr(tech, "bid_ask_spread", None)

    last_audit = None
    try:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        db = get_supabase_client()
        if db:
            res = await db.table("audit_reports").select(
                "report_date, recommendation, "
                "opportunity_score, torpedo_score, "
                "report_text, created_at"
            ).eq("ticker", ticker).gte("report_date", cutoff).order("report_date", desc=True).limit(1).execute_async()
            rows = res.data if res and res.data else []
            if rows: 
                last_audit = {
                    "date": rows[0].get("report_date") or rows[0].get("created_at", ""),
                    "recommendation": rows[0].get("recommendation"),
                    "opportunity_score": rows[0].get("opportunity_score"),
                    "torpedo_score": rows[0].get("torpedo_score"),
                    "report_text": rows[0].get("report_text", "")
                }
    except Exception as e: 
        logger.debug(f"Research: last audit {ticker}: {e}")

    ticker_sent = _calc_sentiment_from_bullets(news_mem or [])
    mkt_cat = market_sent_data.get("category_sentiment", {})
    mkt_scores = [v.get("score", 0.0) for v in mkt_cat.values() if v.get("score") is not None]
    market_avg_sentiment = round(sum(mkt_scores) / len(mkt_scores), 3) if mkt_scores else 0.0
    sentiment_divergence_calc = bool(ticker_sent["count"] > 0 and ticker_sent["avg"] > 0.1 and ticker_sent["trend"] == "deteriorating")

    from backend.app.analysis.scoring import calculate_opportunity_score, calculate_torpedo_score, get_recommendation
    opp_score_obj = torp_score_obj = recommendation_obj = None
    try:
        macro_snap = await get_macro_snapshot()
        valuation_ctx = metrics.dict() if hasattr(metrics, "dict") else (profile.dict() if hasattr(profile, "dict") else {"ticker": effective_ticker, "pe_ratio": pe_ratio, "ps_ratio": ps_ratio, "market_cap": market_cap, "sector": sector})
        data_ctx = {"earnings_history": history.dict() if hasattr(history, "dict") else {}, "valuation": valuation_ctx, "short_interest": short_int.dict() if hasattr(short_int, "dict") else {}, "insider_activity": insiders.dict() if hasattr(insiders, "dict") else {}, "macro": macro_snap.dict() if hasattr(macro_snap, "dict") else {}, "technicals": tech.dict() if hasattr(tech, "dict") else {}, "news_memory": news_mem or [], "options": options.dict() if hasattr(options, "dict") else {}, "web_sentiment_score": 0.0, "finbert_sentiment": ticker_sent["avg"], "sentiment_divergence": sentiment_divergence_calc, "analyst_grades": analyst_grades or [], "sector_ranking": market_ov.get("sector_ranking_5d", []) if market_ov else [], "ticker_sector": sector or "Unknown", "reddit_sentiment": reddit_data.get("avg_score") if reddit_data else None, "reddit_mentions": reddit_data.get("mention_count", 0) if reddit_data else 0}
        opp_score_obj = await calculate_opportunity_score(effective_ticker, data_ctx)
        torp_score_obj = await calculate_torpedo_score(effective_ticker, data_ctx)
        recommendation_obj = await get_recommendation(opp_score_obj, torp_score_obj)
    except Exception as e: logger.warning(f"Research Scoring {effective_ticker}: {e}")

    response = {"ticker": ticker, "resolved_ticker": effective_ticker, "was_resolved": resolution["was_resolved"], "resolution_note": resolution["resolution_note"], "data_quality": resolution["data_quality"], "available_fields": resolution["available_fields"], "company_name": company_name or ticker, "sector": sector, "industry": industry, "fetched_at": now.isoformat(), "company_profile": {"ceo": ceo, "employees": int(employees) if employees else None, "description": (description[:300].rsplit(" ", 1)[0] + "…") if description and len(description) > 300 else description, "website": website, "ipo_date": str(ipo_date) if ipo_date else None, "country": country, "exchange": exchange, "peers": peers_list}, "price": price, "change_pct": change_pct, "price_change_30d": price_change_30d, "price_change_5d": price_change_5d, "fifty_two_week_high": fifty_two_week_high, "fifty_two_week_low": fifty_two_week_low, "pre_market_price": pre_market_price, "post_market_price": post_market_price, "pre_market_change": pre_market_change, "relative_strength": rel_strength, "pe_ratio": pe_ratio, "forward_pe": forward_pe, "ps_ratio": ps_ratio, "peg_ratio": round(peg_ratio, 2) if peg_ratio else None, "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda else None, "market_cap": market_cap, "beta": beta, "dividend_yield": dividend_yield, "revenue_ttm": revenue_ttm, "eps_ttm": eps_ttm, "roe": round(roe * 100, 1) if roe else None, "roa": round(roa * 100, 1) if roa else None, "debt_equity": debt_equity, "fcf_yield": round(fcf_yield * 100, 2) if fcf_yield else None, "current_ratio": current_ratio, "analyst_target": price_target_avg or analyst_target, "analyst_target_high": price_target_high, "analyst_target_low": price_target_low, "analyst_recommendation": analyst_recommendation, "number_of_analysts": number_of_analysts, "rsi": rsi, "trend": trend, "sma_50": sma_50, "sma_200": sma_200, "above_sma50": above_sma50, "above_sma200": above_sma200, "sma50_distance_pct": sma50_distance, "sma200_distance_pct": sma200_distance, "support": support, "resistance": resistance, "distance_52w_high_pct": distance_52w_high, "sma_20": sma_20, "atr_14": atr_14, "macd": macd, "macd_signal": macd_signal_val, "macd_histogram": macd_histogram, "macd_bullish": macd_bullish, "obv_trend": obv_trend, "rvol": rvol, "float_shares": float_shares, "avg_volume": avg_volume, "bid_ask_spread": bid_ask_spread, "iv_atm": round(getattr(options, "implied_volatility_atm", 0) * 100, 1) if options else None, "put_call_ratio": getattr(options, "put_call_ratio_vol", getattr(options, "put_call_ratio_oi", None)) if options else None, "expected_move_pct": expected_move_pct, "expected_move_usd": expected_move_usd, "max_pain": oi_data.get("nearest_max_pain") if oi_data else None, "options_oi_url": f"/api/data/options-oi/{effective_ticker}", "short_interest_pct": short_interest_pct, "days_to_cover": days_to_cover, "squeeze_risk": squeeze_risk, "finra_short_ratio": finra_data.get("short_volume_ratio") if finra_data else None, "squeeze_signal": "high" if ((finra_data.get("short_volume_ratio") or 0) > 0.55 and (short_interest_pct or 0) > 10) else "neutral", "insider_buys": insider_buys, "insider_sells": insider_sells, "insider_buy_value": insider_buy_value, "insider_sell_value": insider_sell_value, "insider_assessment": insider_assessment, "earnings_date": earnings_date, "report_timing": report_timing, "earnings_countdown": earnings_countdown, "earnings_today": earnings_today, "eps_consensus": eps_consensus, "revenue_consensus": revenue_consensus, "beats_of_8": beats_of_8, "avg_surprise_pct": avg_surprise, "last_surprise_pct": last_surprise_pct, "last_beat": last_beat, "quarterly_history": quarterly_history, "news_bullets": news_bullets, "is_watchlist": is_watchlist, "web_prio": watchlist_item.get("web_prio") if watchlist_item else None, "last_audit": last_audit, "opportunity_score": round(opp_score_obj.total_score, 1) if opp_score_obj else None, "torpedo_score": round(torp_score_obj.total_score, 1) if torp_score_obj else None, "recommendation": recommendation_obj.recommendation if recommendation_obj else None, "recommendation_label": recommendation_obj.recommendation_label if recommendation_obj else None, "recommendation_reason": recommendation_obj.reasoning if recommendation_obj else None, "score_breakdown": {"opportunity": {k: round(v, 1) for k, v in opp_score_obj.dict().items() if isinstance(v, (int, float))} if opp_score_obj else {}, "torpedo": {k: round(v, 1) for k, v in torp_score_obj.dict().items() if isinstance(v, (int, float))} if torp_score_obj else {}} if opp_score_obj and torp_score_obj else None, "finbert_sentiment": ticker_sent["avg"], "sentiment_label": ticker_sent["label"], "sentiment_trend": ticker_sent["trend"], "sentiment_has_material": bool(ticker_sent["has_material"]), "sentiment_count": ticker_sent["count"], "sentiment_divergence": sentiment_divergence_calc, "market_sentiment_avg": market_avg_sentiment, "market_sentiment_detail": mkt_cat, "sentiment_vs_market": round(ticker_sent["avg"] - market_avg_sentiment, 3) if (mkt_scores and ticker_sent["count"] > 0) else None, "reddit_sentiment": {"score": reddit_data.get("avg_score"), "mentions": reddit_data.get("mention_count", 0), "label": reddit_data.get("label")} if reddit_data else None, "fear_greed": {"score": fg.get("score"), "label": fg.get("label")} if fg else None, "sector_earnings_upcoming": sector_earnings[:5]}
    core_available = sum(1 for v in [price, pe_ratio, rsi, revenue_ttm, market_cap] if v is not None)
    response["core_fields_available"] = core_available
    response["data_sufficient_for_ai"] = core_available >= 3
    if not response["data_sufficient_for_ai"]: response["ai_blocked_reason"] = f"Nur {core_available}/5 Kernfelder verfügbar. Die KI-Analyse wäre auf falschen oder unvollständigen Daten basiert. Bitte alternativen Ticker eingeben."

    def _json_safe(v):
        if isinstance(v, dict): return {k: _json_safe(val) for k, val in v.items()}
        if isinstance(v, (list, tuple)): return [_json_safe(val) for val in v]
        if hasattr(v, "item") and not isinstance(v, (str, bytes)):
            try: return _json_safe(v.item())
            except: pass
        return v
    response = _json_safe(response)
    cache_set(cache_key, response, ttl_seconds=600)
    return response

@router.get("/earnings-radar")
async def api_earnings_radar(days: int = 14):
    cache_key = f"earnings_radar_{days}"
    cached = cache_get(cache_key)
    if cached: return cached
    now = now_mez()
    from_date, to_date = now.strftime("%Y-%m-%d"), (now + timedelta(days=days)).strftime("%Y-%m-%d")
    
    def _mez_time(hour: str | None) -> str | None:
        """Konvertiert Finnhub hour zu MEZ-Uhrzeit."""
        if hour == "bmo":
            return "07:00 MEZ"
        if hour == "amc":
            return "22:00 MEZ"
        return None
    
    def _get_company_name(ticker: str) -> str | None:
        """Holt Firmennamen via yfinance."""
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            return info.get("shortName") or info.get("longName") or info.get("companyName")
        except Exception:
            return None
    
    cal_result, watchlist = await asyncio.gather(get_earnings_calendar(from_date, to_date), get_watchlist(), return_exceptions=True)
    if isinstance(cal_result, Exception): return {"entries": [], "error": str(cal_result)}
    watchlist = watchlist if isinstance(watchlist, list) else []
    wl_tickers = {w.get("ticker", "").upper() for w in watchlist}
    cross_signal_map = {}
    for w in watchlist:
        for cs in (w.get("cross_signal_tickers") or []):
            cs_upper = cs.upper()
            if cs_upper not in cross_signal_map: cross_signal_map[cs_upper] = []
            cross_signal_map[cs_upper].append(w.get("ticker", "").upper())
    all_tickers = list(wl_tickers) + [cs for cs_list in cross_signal_map.values() for cs in cs_list]
    bullets_by_ticker = await get_bullet_points_batch(all_tickers, limit_per_ticker=10)
    entries = []
    today_str = now.strftime("%Y-%m-%d")
    for item in (cal_result if isinstance(cal_result, list) else []):
        ticker = getattr(item, "ticker", None)
        if not ticker: continue
        ticker = ticker.upper()
        date_str = str(getattr(item, "report_date", None) or "")
        if not date_str: continue
        try:
            from datetime import date as _d
            days_until = (_d.fromisoformat(date_str) - _d.today()).days
        except: days_until = None
        pre_earnings_sentiment = None
        ticker_bullets = bullets_by_ticker.get(ticker, [])
        if ticker_bullets:
            sent = _calc_sentiment_from_bullets(ticker_bullets)
            pre_earnings_sentiment = {"avg": sent["avg"], "label": sent["label"], "trend": sent["trend"], "has_material": sent["has_material"], "count": sent["count"]}
        entry = {
            "ticker": ticker,
            "company_name": _get_company_name(ticker),  # NEU: Firmennamen von yfinance
            "report_date": date_str,
            "report_timing": getattr(item, "report_timing", None),
            "report_hour": getattr(item, "report_hour", None),
            "report_time_mez": _mez_time(getattr(item, "report_hour", None)),
            "eps_consensus": getattr(item, "eps_consensus", None),
            "revenue_consensus": getattr(item, "revenue_consensus", None),
            "is_watchlist": ticker in wl_tickers,
            "cross_signal_for": cross_signal_map.get(ticker, []),
            "is_today": date_str == today_str,
            "days_until": days_until,
            "pre_earnings_sentiment": pre_earnings_sentiment
        }
        entries.append(entry)
    entries.sort(key=lambda e: (e.get("days_until") or 999))
    result = {"entries": entries, "total": len(entries), "from_date": from_date, "to_date": to_date, "watchlist_count": sum(1 for e in entries if e["is_watchlist"]), "today_count": sum(1 for e in entries if e["is_today"])}
    cache_set(cache_key, result, ttl_seconds=600)
    return result

@router.post("/sympathy-check/{reporter}")
async def api_sympathy_check(reporter: str, move_pct: float):
    """Analysiert Peer-Reaktionen nach Earnings."""
    from backend.app.analysis.peer_monitor import check_sympathy_reactions, send_sympathy_alert
    wl = await get_watchlist()
    peers = []
    for item in (wl if isinstance(wl, list) else []):
        cs = item.get("cross_signal_tickers") or item.get("cross_signals") or []
        if reporter.upper() in [c.upper() for c in cs]: peers.append(item["ticker"])
        if item.get("ticker", "").upper() == reporter.upper(): peers.extend([c.upper() for c in cs])
    peers = list(set(peers))
    analysis = await check_sympathy_reactions(reporter.upper(), move_pct, peers)
    await send_sympathy_alert(analysis)
    return analysis

@router.get("/ohlcv/{ticker}")
async def api_ohlcv(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Liefert validierte OHLCV-Daten inkl. SMA50/200."""
    allowed_periods, allowed_intervals = {"1mo", "3mo", "6mo", "1y", "2y"}, {"1d", "1wk"}
    period = period if period in allowed_periods else "6mo"
    interval = interval if interval in allowed_intervals else "1d"
    if period in {"1mo", "3mo"} and interval == "1wk": interval = "1d"
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)
        if hist.empty: return {"ticker": ticker, "period": period, "interval": interval, "candles": [], "sma_50": [], "sma_200": [], "error": "Keine Daten"}
        candles = []
        for ts, row in hist.iterrows(): candles.append({"time": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10], "open": round(float(row["Open"]), 4), "high": round(float(row["High"]), 4), "low": round(float(row["Low"]), 4), "close": round(float(row["Close"]), 4), "volume": int(row["Volume"])})
        close_series, sma_50, sma_200 = hist["Close"], [], []
        if len(close_series) >= 50:
            sma_raw = close_series.rolling(50).mean()
            for ts, val in zip(hist.index, sma_raw):
                if not pd.isna(val): sma_50.append({"time": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10], "value": round(float(val), 4)})
        if len(close_series) >= 200:
            sma_raw = close_series.rolling(200).mean()
            for ts, val in zip(hist.index, sma_raw):
                if not pd.isna(val): sma_200.append({"time": ts.strftime("%Y-%m-%d"), "value": round(float(val), 4)})
        return {"ticker": ticker, "period": period, "interval": interval, "candles": candles, "sma_50": sma_50, "sma_200": sma_200}
    except Exception as exc:
        logger.error(f"OHLCV Error for {ticker}: {exc}")
        return {"ticker": ticker, "period": period, "interval": interval, "candles": [], "sma_50": [], "sma_200": [], "error": str(exc)}

@router.get("/finra-short/{ticker}")
async def api_finra_short(ticker: str):
    return await get_finra_short_volume(ticker.upper())

@router.get("/fear-greed")
async def api_fear_greed():
    return await get_fear_greed_score()

@router.get("/reddit-sentiment/{ticker}")
async def api_reddit_sentiment(ticker: str):
    return await get_reddit_sentiment(ticker.upper())

@router.get("/options-oi/{ticker}")
async def api_options_oi(ticker: str):
    return await get_options_oi_analysis(ticker.upper())

@router.get("/vwap/{ticker}")
async def api_vwap(ticker: str):
    return await get_vwap(ticker.upper())

@router.get("/chart-overlays/{ticker}")
async def api_chart_overlays(ticker: str):
    """Aggregiert Earnings-, Torpedo-, Narrative- und Insider-Events für Charts."""
    db = get_supabase_client()
    base_response = {"earnings_events": [], "torpedo_alerts": [], "narrative_shifts": [], "insider_transactions": []}
    if not db: return base_response
    try:
        reviews = await db.table("earnings_reviews").select("quarter,pre_earnings_report_date,pre_earnings_recommendation,actual_surprise_percent,stock_reaction_1d_percent").eq("ticker", ticker).order("created_at", desc=True).limit(12).execute_async()
        earnings_events = []
        for row in (reviews.data or []):
            dt_str = row.get("pre_earnings_report_date")
            if not dt_str: continue
            surprise = row.get("actual_surprise_percent")
            earnings_events.append({"time": dt_str.split("T")[0], "type": "earnings", "timing": "after_hours", "eps_surprise_pct": surprise, "reaction_1d_pct": row.get("stock_reaction_1d_percent"), "recommendation": row.get("pre_earnings_recommendation"), "label": f"{'Beat' if surprise > 0 else 'Miss'} {surprise:+.1f}%" if surprise is not None else (row.get("pre_earnings_recommendation") or "")})
        
        audits = await db.table("audit_reports").select("report_date,earnings_date,opportunity_score,torpedo_score,recommendation").eq("ticker", ticker).order("report_date", desc=True).limit(8).execute_async()
        def _parse_date(v):
            if not v: return None
            try: return datetime.fromisoformat(v.replace("Z", ""))
            except:
                try: return datetime.strptime(v.split("T")[0], "%Y-%m-%d")
                except: return None
        rev_dates = [_parse_date(r.get("pre_earnings_report_date")) for r in (reviews.data or []) if r.get("pre_earnings_report_date")]
        for audit in (audits.data or []):
            rep_dt = _parse_date(audit.get("report_date"))
            if rep_dt and any(abs((rd - rep_dt).days) < 5 for rd in rev_dates): continue
            time_val = _parse_date(audit.get("earnings_date")) or rep_dt
            if time_val: earnings_events.append({"time": time_val.strftime("%Y-%m-%d"), "type": "earnings", "timing": "after_hours", "eps_surprise_pct": None, "reaction_1d_pct": None, "recommendation": audit.get("recommendation"), "label": audit.get("recommendation") or ""})
        
        torp_rows = await db.table("short_term_memory").select("date,bullet_points,sentiment_score,is_material").eq("ticker", ticker).eq("is_material", True).order("date", desc=True).limit(20).execute_async()
        torpedo_alerts = []
        for row in (torp_rows.data or []):
            bps, score, dt_val = row.get("bullet_points"), row.get("sentiment_score"), row.get("date")
            if not dt_val: continue
            txt = "Material Event"
            if isinstance(bps, list) and bps: txt = str(bps[0])[:150]
            elif isinstance(bps, dict) and bps: txt = str(next(iter(bps.values())))[:150]
            elif isinstance(bps, str): txt = bps[:150]
            torp_score = round(abs(score) * 10, 2) if score is not None and score < -0.3 else 6.0
            torpedo_alerts.append({"time": dt_val.split("T")[0], "type": "torpedo", "event_text": txt, "torpedo_score": torp_score})
        
        narr_rows = await db.table("short_term_memory").select("date,shift_type,shift_reasoning,bullet_points,sentiment_score,is_narrative_shift").eq("ticker", ticker).eq("is_narrative_shift", True).order("date", desc=True).limit(15).execute_async()
        narrative_shifts = []
        for row in (narr_rows.data or []):
            bps, dt_val = row.get("bullet_points"), row.get("date")
            if not dt_val: continue
            fb = ""
            if isinstance(bps, list) and bps: fb = str(bps[0])[:150]
            elif isinstance(bps, dict) and bps: fb = str(next(iter(bps.values())))[:150]
            elif isinstance(bps, str): fb = bps[:150]
            narrative_shifts.append({"time": dt_val.split("T")[0], "type": "narrative_shift", "shift_type": row.get("shift_type"), "summary": (row.get("shift_reasoning") or fb or "Narrative Shift")[:150], "sentiment_delta": row.get("sentiment_score") or 0.0})
        
        ins_data = await get_insider_transactions(ticker)
        txs = getattr(ins_data, "transactions", []) or ins_data.get("transactions", []) if ins_data else []
        insider_transactions = []
        for tx in txs:
            dt_val = tx.get("transactionDate") or tx.get("date")
            if not dt_val: continue
            chg = tx.get("change") or 0
            direc = "buy" if chg > 0 or "p" in (tx.get("transactionType") or "").lower() else "sell"
            insider_transactions.append({"time": dt_val.split("T")[0], "type": "insider", "direction": direc, "name": tx.get("name") or "Insider", "role": tx.get("position") or "", "amount_usd": round(abs(chg) * (tx.get("transactionPrice") or tx.get("price") or 0), 2)})
        
        return {"earnings_events": earnings_events, "torpedo_alerts": torpedo_alerts, "narrative_shifts": narrative_shifts, "insider_transactions": insider_transactions}
    except Exception as exc:
        logger.error(f"chart-overlays Fehler für {ticker}: {exc}")
        return base_response

@router.get("/contrarian-opportunities")
async def api_contrarian_opportunities(min_mismatch_score: float = 50.0):
    """Findet Contrarian-Trading-Opportunities in der Watchlist."""
    logger.info(f"API Call: contrarian-opportunities (min_mismatch_score={min_mismatch_score})")
    try:
        from backend.app.analysis.scoring import calculate_quality_score, calculate_mismatch_score
        watchlist = await get_watchlist()
        opportunities = []
        for item in watchlist:
            ticker = item.get("ticker")
            try:
                news_memory = await get_bullet_points(ticker)
                if not news_memory or not news_memory[:7]: continue
                sent_scores = [b.get("sentiment_score", 0) for b in news_memory[:7] if b.get("sentiment_score") is not None]
                if not sent_scores: continue
                avg_sent = sum(sent_scores) / len(sent_scores)
                if avg_sent >= -0.5: continue
                risk_data = await get_risk_metrics(ticker)
                beta = risk_data.get("beta")
                if beta is None or beta < 1.2: continue
                key_metrics = await get_key_metrics(ticker)
                if not key_metrics: continue
                qual_score = calculate_quality_score(debt_to_equity=key_metrics.debt_to_equity, current_ratio=key_metrics.current_ratio, free_cash_flow_yield=key_metrics.free_cash_flow_yield, pe_ratio=key_metrics.pe_ratio)
                if qual_score < 6.0: continue
                opt_data = await get_atm_implied_volatility(ticker)
                iv_atm, h_vol = (opt_data.implied_volatility_atm, opt_data.historical_volatility) if opt_data else (None, None)
                m_score = calculate_mismatch_score(sentiment_score=avg_sent, quality_score=qual_score, beta=beta, iv_atm=iv_atm, hist_vol=h_vol)
                if m_score < min_mismatch_score: continue
                opportunities.append({"ticker": ticker, "mismatch_score": m_score, "sentiment_7d": round(avg_sent, 3), "quality_score": qual_score, "beta": beta, "iv_atm": iv_atm, "hist_vol": h_vol, "iv_spread": round(iv_atm - h_vol, 2) if (iv_atm and h_vol) else None, "material_news_count": sum(1 for b in news_memory[:7] if b.get("is_material", False)), "debt_to_equity": key_metrics.debt_to_equity, "current_ratio": key_metrics.current_ratio, "fcf_yield": key_metrics.free_cash_flow_yield})
            except: continue
        opportunities.sort(key=lambda x: x["mismatch_score"], reverse=True)
        return {"status": "success", "count": len(opportunities), "opportunities": opportunities}
    except Exception as e:
        logger.error(f"Contrarian-Opportunities Fehler: {e}")
        return {"status": "error", "message": str(e), "opportunities": []}

@router.get("/market-overview")
async def api_market_overview():
    return await get_market_overview()

@router.get("/market-breadth")
async def api_market_breadth():
    return await get_market_breadth()

@router.get("/intermarket")
async def api_intermarket():
    return await get_intermarket_signals()

@router.get("/market-news-sentiment")
async def api_market_news_sentiment():
    return await get_market_news_for_sentiment()

@router.get("/economic-calendar")
async def api_economic_calendar():
    logger.info("API Call: economic-calendar")
    try:
        db = get_supabase_client()
        if not db: return {"events": []}
        now = datetime.utcnow()
        res = await db.table("short_term_memory").select("*").eq("ticker", "GENERAL_MACRO").gte("date", now.isoformat()).lte("date", (now + timedelta(hours=48)).isoformat()).order("date").limit(10).execute_async()
        events = []
        for row in (res.data or []):
            bps = row.get("bullet_points", {})
            if isinstance(bps, dict): events.append({"title": bps.get("event", "Makro-Event"), "date": row.get("date"), "impact": bps.get("impact", "medium"), "country": bps.get("country", "US"), "actual": bps.get("actual"), "estimate": bps.get("estimate")})
        return {"events": events}
    except Exception as e:
        logger.warning(f"Economic Calendar: {e}")
        return {"events": []}

@router.get("/scoring-config")
async def api_scoring_config():
    import yaml, os
    cp = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "scoring.yaml")
    try:
        with open(cp, "r", encoding="utf-8") as f: return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Scoring config load error: {e}")
        return {"error": "config_not_found"}

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

@router.get("/performance")
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

@router.get("/options/{ticker}", response_model=OptionsData)
async def api_options_data(ticker: str):
    """Holt Options-Daten inkl. IV ATM, Put/Call Ratio, historischer Volatilität."""
    logger.info(f"API Call: options-data for {ticker}")
    options_data = await get_atm_implied_volatility(ticker)
    if options_data is None:
        return OptionsData(ticker=ticker)
    return options_data

@router.get("/risk-metrics/{ticker}")
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

@router.get("/score-delta/{ticker}")
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

@router.get("/sparkline/{ticker}")
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

@router.get("/quick-snapshot/{ticker}")
async def api_quick_snapshot(ticker: str):
    ticker = ticker.upper().strip()
    cache_key = f"quick_snapshot_{ticker}"
    cached = cache_get(cache_key)
    if cached:
        return cached

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

@router.get("/volume-profile/{ticker}")
async def api_volume_profile(ticker: str):
    """
    Holt 20-Tage Volumen-Profil für Visualisierung.
    Returns: [{date, volume, close, change_pct, color}, ...]
    """
    ticker = ticker.upper().strip()
    
    try:
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

@router.get("/research/{ticker}")
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

    # ── Ticker Resolver ────────────────────────────────────────
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
        yf_history = await get_earnings_history_yf(
            effective_ticker
        )
        if yf_history:
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
        from datetime import date
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
            eps_act = getattr(q, "eps_actual", None)
            eps_cons = getattr(q, "eps_consensus", None)
            surp_pct = getattr(q, "eps_surprise_percent", None)
            reac_1d = getattr(q, "stock_reaction_1d", None)
            quarterly_history.append({
                "quarter": getattr(q, "quarter", ""),
                "eps_actual": float(eps_act) if eps_act is not None else None,
                "eps_consensus": float(eps_cons) if eps_cons is not None else None,
                "surprise_pct": float(surp_pct) if surp_pct is not None else None,
                "reaction_1d": float(reac_1d) if reac_1d is not None else None,
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
                price_change_30d = (
                    yf_fund.get("change_1m_pct")
                    if isinstance(yf_fund, dict) else None
                )
    except Exception:
        price_change_30d = None

    # ── Relative Stärke berechnen ───────────────────────────────
    market_ov = market_ov or {}
    indices_data = market_ov.get("indices", {})
    sector_ranking_map = {
        s["symbol"]: s
        for s in market_ov.get("sector_ranking_5d", [])
    }

    spy_data = indices_data.get("SPY", {})

    # Sektor-ETF für diesen Ticker
    sector_etf_symbol = SECTOR_TO_ETF.get(sector or "", None)
    sector_etf_data = (
        sector_ranking_map.get(sector_etf_symbol, {})
        if sector_etf_symbol else {}
    )
    sector_etf_full = indices_data.get(sector_etf_symbol, {})

    def relative_strength(ticker_pct, bench_pct):
        if ticker_pct is None or bench_pct is None:
            return None
        return round(ticker_pct - bench_pct, 2)

    # 5-Tage Performance für den Ticker
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

    if not short_interest_pct:
        try:
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
    for b in (news_mem or [])[:8]:
        news_bullets.append({
            "text": b.get("bullet_text", "") or b.get("insight", ""),
            "sentiment": b.get("sentiment_score", 0),
            "is_material": b.get("is_material", False),
            "category": b.get("category", "News"),
            "date": b.get("date", "") or b.get("created_at", ""),
            "source": "finbert",
        })

    if len(news_bullets) < 5 and news_items:
        for item in (news_items or [])[:8]:
            headline = item.get("headline", "") if isinstance(item, dict) else ""
            if not headline:
                continue
            published = item.get("datetime", 0)
            date_str = (
                datetime.fromtimestamp(published).strftime("%Y-%m-%d")
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
    price_target_avg = None
    if price_tgt:
        price_target_high = price_tgt.get("targetHigh") or price_tgt.get("targetHighPrice")
        price_target_low  = price_tgt.get("targetLow") or price_tgt.get("targetLowPrice")
        price_target_avg  = price_tgt.get("targetConsensus") or price_tgt.get("targetMeanPrice")
    if not price_target_avg and analyst_target:
        price_target_avg = analyst_target

    # ── Technicals zusammenführen ──────────────────────────────
    rsi = trend = sma_50 = sma_200 = above_sma50 = above_sma200 = None
    sma50_distance = sma200_distance = support = resistance = distance_52w_high = None
    sma_20 = atr_14 = macd = macd_signal_val = macd_histogram = macd_bullish = None
    obv = obv_trend = rvol = float_shares = avg_volume = bid_ask_spread = None

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
    ticker_sent = _calc_sentiment_from_bullets(news_mem or [])
    mkt_cat = market_sent_data.get("category_sentiment", {})
    mkt_scores = [v.get("score", 0.0) for v in mkt_cat.values() if v.get("score") is not None]
    market_avg_sentiment = round(sum(mkt_scores) / len(mkt_scores), 3) if mkt_scores else 0.0
    sentiment_divergence_calc = bool(ticker_sent["count"] > 0 and ticker_sent["avg"] > 0.1)

    # ── Finale Antwort ─────────────────────────────────────────
    response = {
        "ticker": ticker,
        "effective_ticker": effective_ticker,
        "resolution": resolution,
        "is_watchlist": is_watchlist,
        "watchlist_item": watchlist_item,
        "company_name": company_name or ticker,
        "sector": sector,
        "industry": industry,
        "country": country,
        "exchange": exchange,
        "price": price,
        "change_pct": change_pct,
        "pre_market_price": pre_market_price,
        "post_market_price": post_market_price,
        "pre_market_change": pre_market_change,
        "expected_move": {
            "pct": expected_move_pct,
            "usd": expected_move_usd,
            "iv": round((getattr(options, 'implied_volatility_atm', 0) or 0) * 100, 1) if options else None,
        },
        "fundamentals": {
            "pe_ratio": pe_ratio,
            "forward_pe": forward_pe,
            "ps_ratio": ps_ratio,
            "peg_ratio": peg_ratio,
            "ev_ebitda": ev_ebitda,
            "roe": roe,
            "roa": roa,
            "debt_equity": debt_equity,
            "fcf_yield": fcf_yield,
            "current_ratio": current_ratio,
            "market_cap": market_cap,
            "beta": beta,
            "dividend_yield": dividend_yield,
            "revenue_ttm": revenue_ttm,
            "eps_ttm": eps_ttm,
            "ceo": ceo,
            "employees": employees,
            "description": description,
            "website": website,
            "ipo_date": ipo_date,
            "peers": peers_list,
        },
        "technicals": {
            "rsi": rsi,
            "trend": trend,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "above_sma50": above_sma50,
            "above_sma200": above_sma200,
            "sma50_distance": sma50_distance,
            "sma200_distance": sma200_distance,
            "support": support,
            "resistance": resistance,
            "fifty_two_week_high": fifty_two_week_high,
            "fifty_two_week_low": fifty_two_week_low,
            "distance_52w_high": distance_52w_high,
            "sma_20": sma_20,
            "atr_14": atr_14,
            "macd": macd,
            "macd_signal": macd_signal_val,
            "macd_histogram": macd_histogram,
            "macd_bullish": macd_bullish,
            "obv": obv,
            "obv_trend": obv_trend,
            "rvol": rvol,
            "float_shares": float_shares,
            "avg_volume": avg_volume,
            "bid_ask_spread": bid_ask_spread,
        },
        "earnings": {
            "next_date": earnings_date,
            "timing": report_timing,
            "countdown": earnings_countdown,
            "is_today": earnings_today,
            "eps_consensus": eps_consensus,
            "revenue_consensus": revenue_consensus,
            "beats_of_8": beats_of_8,
            "avg_surprise_pct": avg_surprise,
            "last_surprise_pct": last_surprise_pct,
            "last_beat": last_beat,
            "history": quarterly_history,
            "sector_calendar": sector_earnings,
        },
        "analyst": {
            "target_avg": price_target_avg,
            "target_high": price_target_high,
            "target_low": price_target_low,
            "recommendation": analyst_recommendation,
            "analyst_count": number_of_analysts,
            "upside_pct": round((price_target_avg - price) / price * 100, 1) if price_target_avg and price else None,
        },
        "sentiment": {
            "ticker_sentiment": ticker_sent["avg"],
            "ticker_sentiment_label": ticker_sent["trend"],
            "ticker_article_count": ticker_sent["count"],
            "market_avg_sentiment": market_avg_sentiment,
            "reddit_sentiment": reddit_data.get("sentiment_score") if reddit_data else 0.0,
            "reddit_mentions": reddit_data.get("mention_count") if reddit_data else 0,
            "fear_greed_score": fg.get("score") if fg else 50,
            "fear_greed_label": fg.get("label") if fg else "neutral",
            "divergence": sentiment_divergence_calc,
            "news": news_bullets,
        },
        "smart_money": {
            "short_interest_pct": short_interest_pct,
            "days_to_cover": days_to_cover,
            "squeeze_risk": squeeze_risk,
            "insider_buys": insider_buys,
            "insider_sells": insider_sells,
            "insider_buy_value": insider_buy_value,
            "insider_sell_value": insider_sell_value,
            "insider_assessment": insider_assessment,
            "finra_short_vol_pct": finra_data.get("short_vol_pct") if finra_data else None,
            "max_pain": oi_data.get("max_pain") if oi_data else None,
            "pcr_volume": oi_data.get("pcr_volume") if oi_data else None,
        },
        "relative_strength": rel_strength,
        "last_audit": last_audit,
        "timestamp": datetime.now().isoformat(),
    }

    cache_set(cache_key, response, ttl_seconds=600)
    return response

@router.get("/earnings-radar")
async def api_earnings_radar(days: int = 14):
    from datetime import datetime, timedelta
    from backend.app.data.finnhub import get_earnings_calendar
    from backend.app.memory.watchlist import get_watchlist
    
    today = datetime.now()
    end_date = today + timedelta(days=days)
    
    try:
        results = await asyncio.gather(
            get_earnings_calendar(today.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
            get_watchlist(),
            return_exceptions=True
        )
        
        calendar = results[0] if not isinstance(results[0], Exception) else []
        watchlist = results[1] if not isinstance(results[1], Exception) else []
        
        watchlist_tickers = {w["ticker"].upper() for w in watchlist}
        
        radar_items = []
        for event in (calendar or []):
            ticker = getattr(event, "ticker", "").upper()
            if ticker in watchlist_tickers:
                radar_items.append({
                    "ticker": ticker,
                    "date": str(getattr(event, "report_date", "")),
                    "timing": getattr(event, "report_timing", "unknown"),
                    "eps_est": getattr(event, "eps_consensus", None),
                    "rev_est": getattr(event, "revenue_consensus", None),
                })
        
        radar_items.sort(key=lambda x: x["date"])
        return {"status": "success", "count": len(radar_items), "items": radar_items}
    except Exception as e:
        logger.error(f"Earnings Radar Fehler: {e}")
        return {"status": "error", "message": str(e)}
