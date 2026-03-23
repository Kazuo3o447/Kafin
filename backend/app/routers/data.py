from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Any
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import asyncio
from types import SimpleNamespace

from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set, cache_invalidate
from backend.app.db import get_supabase_client
from backend.app.data.finnhub import (
    get_earnings_calendar, get_company_news, get_short_interest, get_insider_transactions,
    get_economic_calendar,
)
from backend.app.data.fmp import (
    get_company_profile, get_analyst_estimates, get_earnings_history, get_key_metrics,
    get_price_target_consensus, get_analyst_grades
)
from backend.app.data.fred import get_macro_snapshot
from backend.app.data.fear_greed import get_fear_greed_score
from backend.app.data.yfinance_data import (
    get_risk_metrics, get_atm_implied_volatility, get_historical_volatility,
    get_technical_setup, get_fundamentals_yf, get_options_metrics, get_options_oi_analysis,
    get_earnings_history_yf, get_short_interest_yf, get_vwap
)
from backend.app.data.ticker_resolver import resolve_ticker
from backend.app.data.finra import get_finra_short_volume
from backend.app.data.reddit_monitor import get_reddit_sentiment
from backend.app.data.market_overview import get_market_overview, get_market_news_for_sentiment, get_market_breadth, get_intermarket_signals
from backend.app.memory.long_term import get_insights
from backend.app.memory.short_term import get_bullet_points, _calc_sentiment_from_bullets, get_bullet_points_batch
from backend.app.memory.watchlist import get_watchlist
from backend.app.utils.timezone import now_mez
from backend.app.utils.constants import SECTOR_TO_ETF

# NEU: ETF/Index Konstanten
ETF_TICKERS = {
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "GLD", "SLV",
    "USO", "TLT", "HYG", "LQD", "XLF", "XLE", "XLK", "XLI",
    "XLV", "XLP", "XLU", "XLK", "XLY", "XLB", "XLRE", "XLC"
}

INDEX_TICKERS = {
    "^SPX", "^NDX", "^DJI", "^RUT", "^VIX", "VIX", "DXY",
    "DX", "^TNX", "TYX", "^IRX", "^FVX", "^DJI"
}

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


@router.get("/market-overview")
async def api_market_overview():
    logger.info("API Call: market-overview")
    return await get_market_overview()


@router.get("/market-breadth")
async def api_market_breadth():
    logger.info("API Call: market-breadth")
    return await get_market_breadth()


@router.get("/intermarket")
async def api_intermarket():
    logger.info("API Call: intermarket")
    return await get_intermarket_signals()


@router.get("/market-news-sentiment")
async def api_market_news_sentiment():
    logger.info("API Call: market-news-sentiment")
    return await get_market_news_for_sentiment()


@router.get("/economic-calendar")
async def api_economic_calendar(days_back: int = 7, days_forward: int = 7):
    logger.info(f"API Call: economic-calendar {days_back=} {days_forward=}")
    events = await get_economic_calendar(days_back=days_back, days_forward=days_forward)
    return {"events": events}


@router.get("/fear-greed")
async def api_fear_greed():
    logger.info("API Call: fear-greed")
    return await get_fear_greed_score()

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
    cached = await cache_get(cache_key)
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
    await cache_set(cache_key, response, ttl_seconds=300)
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
    cached = await cache_get(cache_key)
    if cached:
        return cached
    try:
        def _get_stock():
            return yf.Ticker(ticker)

        stock = await asyncio.to_thread(_get_stock)

        def _get_hist():
            return stock.history(period=f"{max(days, 2)}d")

        hist = await asyncio.to_thread(_get_hist)
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
        await cache_set(cache_key, result, ttl_seconds=300)
        return result
    except Exception as e:
        logger.debug(f"Sparkline Fehler für {ticker}: {e}")
        return {"ticker": ticker, "data": []}

@router.get("/quick-snapshot/{ticker}")
async def api_quick_snapshot(ticker: str):
    ticker = ticker.upper().strip()
    cache_key = f"quick_snapshot_{ticker}"
    cached = await cache_get(cache_key)
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
            def _get_stock():
                return yf.Ticker(ticker)

            stock = await asyncio.to_thread(_get_stock)
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

        await cache_set(cache_key, snapshot, ttl_seconds=300)
        return snapshot
    except Exception as e:
        return {"ticker": ticker, "error": str(e), "price": None}

@router.get("/volume-profile/{ticker}")
async def api_volume_profile(ticker: str):
    """Holt 20-Tage Volumen-Profil für Visualisierung."""
    ticker = ticker.upper().strip()
    days = 20
    try:
        def _fetch_volume_data():
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{days}d")
            if hist.empty or len(hist) < 2:
                return []
            hist["change_pct"] = hist["Close"].pct_change() * 100
            result = []
            for idx, row in hist.iterrows():
                try:
                    date_value = idx.date() if hasattr(idx, "date") else idx
                except Exception:
                    date_value = str(idx)
                result.append({
                    "date": str(date_value),
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

@router.get("/peer-comparison/{ticker}")
async def api_peer_comparison(ticker: str):
    """
    Liefert Bewertungs- und Momentum-Kennzahlen für den Hauptticker
    und seine Peers (max 5). Nutzt yfinance + bestehende Hilfsfunktionen.
    Cache: 2h TTL.
    """
    ticker = ticker.upper().strip()
    cache_key = f"peer_comparison:{ticker}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    try:
        from backend.app.data.fmp import get_company_profile
        profile = await get_company_profile(ticker)
        raw_peers = getattr(profile, "peers", None) or []
        peers = [str(p).upper() for p in raw_peers[:5]]
    except Exception:
        peers = []

    all_tickers = [ticker] + peers

    def _fetch_one_sync(t: str) -> dict:
        try:
            stock = yf.Ticker(t)
            info = stock.info or {}
            hist = stock.history(period="5d")
            change_5d = None
            if len(hist) >= 2:
                change_5d = round(
                    (float(hist["Close"].iloc[-1]) - float(hist["Close"].iloc[0]))
                    / float(hist["Close"].iloc[0]) * 100, 2
                )
            avg_vol = float(hist["Volume"].mean()) if not hist.empty else None
            last_vol = float(hist["Volume"].iloc[-1]) if not hist.empty else None
            rvol = round(last_vol / avg_vol, 2) if avg_vol and avg_vol > 0 else None

            return {
                "ticker": t,
                "name": (info.get("shortName") or info.get("longName") or t)[:22],
                "price": round(float(info.get("currentPrice") or info.get("regularMarketPrice") or 0), 2),
                "change_5d_pct": change_5d,
                "pe_ratio": round(float(info["trailingPE"]), 1) if info.get("trailingPE") else None,
                "forward_pe": round(float(info["forwardPE"]), 1) if info.get("forwardPE") else None,
                "ps_ratio": round(float(info["priceToSalesTrailing12Months"]), 1) if info.get("priceToSalesTrailing12Months") else None,
                "market_cap_b": round(float(info["marketCap"]) / 1e9, 1) if info.get("marketCap") else None,
                "rvol": rvol,
            }
        except Exception as e:
            logger.warning(f"peer_comparison fetch failed for {t}: {e}")
            return {"ticker": t, "name": t, "price": None, "change_5d_pct": None,
                    "pe_ratio": None, "forward_pe": None, "ps_ratio": None,
                    "market_cap_b": None, "rvol": None}

    results = await asyncio.gather(*[asyncio.to_thread(_fetch_one_sync, t) for t in all_tickers])
    response = {"main": ticker, "peers": list(results)}
    await cache_set(cache_key, response, ttl_seconds=7200)
    return response

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
        cached = await cache_get(cache_key)
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

    await cache_set(cache_key, response, ttl_seconds=600)
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


@router.get("/filing-diff/{ticker}")
async def api_filing_diff(
    ticker: str,
    filing_type: str = "10-Q",
):
    """
    Tonalitäts-Diff zwischen letzten zwei
    10-Q oder 10-K Berichten via Gemini Flash.
    Cache: 24h.
    Benötigt: GEMINI_API_KEY in .env
    """
    from backend.app.analysis.filing_rag import (
        get_filing_diff
    )
    return await get_filing_diff(
        ticker.upper(),
        filing_type=filing_type.upper(),
    )


def _is_market_hours() -> bool:
    """True if US market is open in Berlin time."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Berlin")
    except Exception:
        tz = None

    now = datetime.now(tz) if tz is not None else datetime.now()
    if now.weekday() >= 5:
        return False
    open_time = now.replace(hour=15, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=22, minute=0, second=0, microsecond=0)
    return open_time <= now <= close_time


def _signal_feed_defaults() -> dict:
    return {
        "torpedo_delta_min": 1.5,
        "material_event": 1,
        "earnings_urgent_days": 5,
        "sma50_break_downtrend": 1,
        "narrative_shift": 1,
        "sentiment_break": 0.1,
        "rvol_min": 2.0,
        "earnings_warning_days": 14,
        "opp_delta_min": 1.5,
        "rsi_oversold": 30.0,
        "rsi_overbought": 70.0,
        "feed_max_signals": 10,
        "dedup_hours": 24,
        "quiet_period_pre_earnings_days": 2,
    }


async def _load_signal_feed_config() -> dict:
    cfg = _signal_feed_defaults()
    db = get_supabase_client()
    if not db:
        return cfg

    try:
        res = await db.table("signal_feed_config").select("key,value").execute_async()
        rows = res.data or []
        for row in rows:
            key = row.get("key")
            value = row.get("value")
            if key in cfg and isinstance(value, dict) and value.get("enabled", True):
                cfg[key] = value.get("value", cfg[key])
    except Exception as exc:
        logger.warning(f"signal_feed_config load failed: {exc}")
    return cfg


def _build_signal_entry(
    ticker: str,
    signal_type: str,
    priority: int,
    headline: str,
    item: dict,
    value: float | int | None = None,
    threshold: float | int | None = None,
) -> dict:
    return {
        "ticker": ticker,
        "signal_type": signal_type,
        "priority": priority,
        "headline": headline,
        "value": value,
        "threshold": threshold,
        "generated_at": datetime.utcnow().isoformat(),
        "source": "watchlist",
        "_item": item,
    }


def _compose_signal_bullets(item: dict, signal: dict) -> list[str]:
    bullets = []
    ticker = signal.get("ticker", "?")
    opp = item.get("opportunity_score")
    torp = item.get("torpedo_score")
    rsi = item.get("rsi")
    trend = item.get("trend") or "neutral"
    rvol = item.get("rvol")
    earnings = item.get("earnings_countdown")
    sentiment = item.get("sentiment_trend") or item.get("finbert_sentiment")

    bullets.append(f"• {ticker}: {signal.get('headline', 'Signal')[:90]}")
    bullets.append(
        f"• Opp {opp if opp is not None else 'n/a'} | Torpedo {torp if torp is not None else 'n/a'} | RSI {rsi if rsi is not None else 'n/a'}"
    )
    if earnings is not None:
        bullets.append(f"• Earnings in {earnings}T | Trend {trend} | RVOL {rvol if rvol is not None else 'n/a'}x")
    else:
        bullets.append(f"• Trend {trend} | RVOL {rvol if rvol is not None else 'n/a'}x | Sentiment {sentiment if sentiment is not None else 'n/a'}")
    return bullets[:3]


@router.get("/signals/feed")
async def api_signals_feed(force_refresh: bool = False):
    """
    Signal Feed: erzeugt aktuelle Watchlist-Anomalien + Preparation Setups.
    Cache: 5 Minuten.
    """
    cache_key = "signals:feed"
    if force_refresh:
        await cache_invalidate(cache_key)

    cached = await cache_get(cache_key)
    if cached:
        return cached

    cfg = await _load_signal_feed_config()
    watchlist = await get_watchlist()
    macro = await get_macro_snapshot()
    macro_dict = macro.dict() if hasattr(macro, "dict") else (macro or {})
    in_market = _is_market_hours()
    generated_at = datetime.utcnow().isoformat()
    max_signals = int(cfg.get("feed_max_signals", 10))
    dedup_hours = int(cfg.get("dedup_hours", 24))
    quiet_days = int(cfg.get("quiet_period_pre_earnings_days", 2))

    raw_signals: list[dict] = []
    preparation_setups: list[dict] = []

    for item in watchlist or []:
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper().strip()
        if not ticker:
            continue

        w_torp = item.get("week_torp_delta") or 0
        w_opp = item.get("week_opp_delta") or 0
        rvol = item.get("rvol") or 0
        above_sma = item.get("above_sma50")
        trend = item.get("trend") or ""
        has_material = bool(item.get("has_material_news"))
        sentiment_trend = item.get("sentiment_trend") or ""
        sentiment_score = item.get("finbert_sentiment") or 0
        rsi = item.get("rsi") or 50
        earnings_days = item.get("earnings_countdown")
        in_quiet = earnings_days is not None and 0 <= earnings_days <= quiet_days

        def add_signal(signal_type: str, priority: int, headline: str, value=None, threshold=None):
            raw_signals.append(
                _build_signal_entry(
                    ticker=ticker,
                    signal_type=signal_type,
                    priority=priority,
                    headline=headline,
                    item=item,
                    value=value,
                    threshold=threshold,
                )
            )

        if w_torp >= float(cfg.get("torpedo_delta_min", 1.5)):
            add_signal("torpedo_rising", 1, f"Torpedo +{w_torp:.1f} diese Woche — Risiko steigt", w_torp, cfg.get("torpedo_delta_min", 1.5))

        if has_material:
            add_signal("material_event", 1, "⚡ Material Event erkannt", 1, 1)

        if earnings_days is not None and 0 <= earnings_days <= int(cfg.get("earnings_urgent_days", 5)):
            add_signal("earnings_urgent", 1, f"Earnings in {earnings_days}T — kurzfristig kritisch", earnings_days, cfg.get("earnings_urgent_days", 5))

        if in_market and not in_quiet and above_sma is False and trend == "downtrend":
            add_signal("sma50_break", 1, "Unter SMA50 gefallen — technischer Bruch", 0, 1)

        if in_market and sentiment_trend == "deteriorating" and sentiment_score > float(cfg.get("sentiment_break", 0.1)):
            add_signal("sentiment_break", 2, f"Sentiment dreht bearish bei {sentiment_score:.2f}", sentiment_score, cfg.get("sentiment_break", 0.1))

        if in_market and not in_quiet and rvol >= float(cfg.get("rvol_min", 2.0)):
            add_signal("rvol_spike", 2, f"RVOL {rvol:.1f}x — erhöhte Aktivität", rvol, cfg.get("rvol_min", 2.0))

        if earnings_days is not None and int(cfg.get("earnings_urgent_days", 5)) < earnings_days <= int(cfg.get("earnings_warning_days", 14)):
            add_signal("earnings_warning", 2, f"Earnings in {earnings_days} Tagen — vorbereiten", earnings_days, cfg.get("earnings_warning_days", 14))

        if w_torp <= 0 and w_opp >= float(cfg.get("opp_delta_min", 1.5)):
            add_signal("setup_improving", 3, f"Opp-Score +{w_opp:.1f} diese Woche", w_opp, cfg.get("opp_delta_min", 1.5))

        if in_market and not in_quiet:
            if rsi <= float(cfg.get("rsi_oversold", 30.0)):
                add_signal("rsi_oversold", 3, f"RSI {rsi:.0f} — überverkauft", rsi, cfg.get("rsi_oversold", 30.0))
            elif rsi >= float(cfg.get("rsi_overbought", 70.0)):
                add_signal("rsi_overbought", 3, f"RSI {rsi:.0f} — überkauft", rsi, cfg.get("rsi_overbought", 70.0))

        if not in_market and earnings_days is not None and 0 <= earnings_days <= 7:
            preparation_setups.append(
                {
                    "ticker": ticker,
                    "name": item.get("name") or item.get("company_name") or ticker,
                    "earnings_date": item.get("earnings_date") or item.get("report_date"),
                    "analysis": f"Vorbereitung auf Earnings in {earnings_days}T: {ticker}",
                    "interest_score": round(float((item.get("opportunity_score") or 0) + (item.get("torpedo_score") or 0)), 1),
                }
            )

    raw_signals.sort(key=lambda sig: (sig["priority"], -abs(float(sig.get("value") or 0))))

    history_cache_key = "signals:history:24h"
    previous_history = await cache_get(history_cache_key) or []
    active_keys = {(sig["ticker"], sig["signal_type"]) for sig in raw_signals}

    resolved_signals = []
    for old in previous_history:
        if not isinstance(old, dict):
            continue
        key = (old.get("ticker"), old.get("signal_type"))
        if key not in active_keys:
            resolved_signals.append({
                **old,
                "is_resolved": True,
                "is_new": False,
            })

    enriched_signals = []
    for sig in raw_signals[:max_signals]:
        dedup_key = f"signals:dedup:{sig['ticker']}:{sig['signal_type']}"
        is_new = await cache_get(dedup_key) is None
        sig["is_new"] = is_new
        sig["is_resolved"] = False
        sig["bullets"] = _compose_signal_bullets(sig.get("_item", {}), sig)
        sig.pop("_item", None)
        enriched_signals.append(sig)
        if is_new:
            await cache_set(dedup_key, True, ttl_seconds=dedup_hours * 3600)

    if not preparation_setups:
        preparation_setups = [
            {
                "ticker": item.get("ticker"),
                "name": item.get("name") or item.get("company_name") or item.get("ticker"),
                "earnings_date": item.get("earnings_date") or item.get("report_date"),
                "analysis": "Keine unmittelbaren Prep-Setups.",
                "interest_score": round(float((item.get("opportunity_score") or 0) + (item.get("torpedo_score") or 0)), 1),
            }
            for item in (watchlist or [])[:3]
            if isinstance(item, dict) and item.get("ticker")
        ]

    if enriched_signals:
        top = enriched_signals[0]
        today_synthesis = (
            f"{len(enriched_signals)} aktive Signale. Schwerpunkt: {top['ticker']} / {top['signal_type']}. "
            f"Regime: {macro_dict.get('regime', 'UNKNOWN')}."
        )
        action_brief = (
            f"Priorisiere {top['ticker']} ({top['signal_type']}). "
            f"Prüfe nur die stärksten drei Setups und meide neue Positionen in ruhigen Namen."
        )
    else:
        today_synthesis = f"Keine Anomalien aktiv. Regime: {macro_dict.get('regime', 'UNKNOWN')}."
        action_brief = "Keine aktiven Signalschwerpunkte. Monitoring fortsetzen."

    current_history = [
        {
            "ticker": sig["ticker"],
            "signal_type": sig["signal_type"],
            "headline": sig["headline"],
            "priority": sig["priority"],
            "bullets": sig.get("bullets", []),
            "generated_at": sig["generated_at"],
        }
        for sig in enriched_signals
    ]
    await cache_set(history_cache_key, current_history, ttl_seconds=86400)

    response = {
        "signals": enriched_signals,
        "resolved_signals": resolved_signals[:5],
        "preparation_setups": preparation_setups[:3],
        "today_synthesis": today_synthesis,
        "action_brief": action_brief,
        "is_market_hours": in_market,
        "total_count": len(enriched_signals),
        "tickers_monitored": len(watchlist or []),
        "feed_generated_at": generated_at,
        "oldest_data_at": generated_at,
        "config_snapshot": cfg,
        "macro_regime": macro_dict.get("regime", "UNKNOWN"),
    }
    await cache_set(cache_key, response, ttl_seconds=300)
    return response


@router.get("/signal-feed-config")
async def api_get_signal_feed_config():
    db = get_supabase_client()
    if not db:
        return {"config": _signal_feed_defaults()}
    try:
        res = await db.table("signal_feed_config").select("*").execute_async()
        rows = res.data or []
        cfg = _signal_feed_defaults()
        for row in rows:
            key = row.get("key")
            value = row.get("value")
            if key in cfg and isinstance(value, dict):
                if value.get("enabled", True):
                    cfg[key] = value.get("value", cfg[key])
        return {"config": cfg}
    except Exception as exc:
        return {"config": _signal_feed_defaults(), "error": str(exc)}


@router.post("/signal-feed-config")
async def api_save_signal_feed_config(body: dict):
    db = get_supabase_client()
    if not db:
        raise HTTPException(status_code=503, detail="DB nicht verfügbar")

    try:
        payload = body.get("config") if isinstance(body.get("config"), dict) else body
        for key, value in payload.items():
            row_value = value if isinstance(value, dict) else {"value": value, "enabled": True}
            await db.table("signal_feed_config").upsert(
                {
                    "key": key,
                    "value": row_value,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                on_conflict="key",
            ).execute_async()
        await cache_invalidate("signals:feed")
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
