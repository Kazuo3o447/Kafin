from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio

from backend.app.logger import get_logger
from backend.app.cache import cache_get, cache_set, cache_invalidate, cache_invalidate_prefix
from backend.app.db import get_supabase_client
from backend.app.memory.watchlist import (
    get_watchlist, add_ticker, remove_ticker, update_ticker, get_earnings_this_week
)
from backend.app.memory.short_term import (
    get_bullet_points_batch,
    _calc_sentiment_from_bullets,
)
from backend.app.data.alpaca_data import get_snapshots as alpaca_get_snapshots

logger = get_logger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

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

def _fetch_ticker_data_sync(ticker: str, entry: dict) -> dict:
    """
    Synchrone Hilfsfunktion für yfinance-Calls mit Cache.
    Wird via asyncio.to_thread() im Thread-Pool ausgeführt.
    """
    import yfinance as yf
    from datetime import datetime as dt
    
    days = 5  # Standardwert für history-Aufrufe

    # Cache-Check
    cache_key = f"yf:enriched_v2:{ticker.upper()}"
    cached_data = cache_get(cache_key)
    if cached_data:
        entry.update(cached_data)
        return entry

    def _get_stock():
        return yf.Ticker(ticker)

    stock = _get_stock()
    result = {}

    # --- Kursdaten via fast_info ---
    try:
        def _get_fast_info():
            return stock.fast_info

        fi = _get_fast_info()
        try:
            if fi.last_price:
                result["price"] = round(float(fi.last_price), 2)
        except Exception:
            pass
        try:
            val = fi.regular_market_day_change_percent
            if val is not None:
                result["change_pct"] = round(float(val) * 100, 2)
        except Exception:
            pass
        try:
            if fi.market_cap:
                result["market_cap_b"] = round(float(fi.market_cap) / 1e9, 1)
        except Exception:
            pass
        # Pre/Post-Market Daten
        try:
            if fi.pre_market_price:
                result["pre_market_price"] = round(float(fi.pre_market_price), 2)
        except Exception:
            pass
        try:
            if fi.pre_market_change_percent:
                result["pre_market_change"] = round(float(fi.pre_market_change_percent), 2)
        except Exception:
            pass
        try:
            if fi.post_market_price:
                result["post_market_price"] = round(float(fi.post_market_price), 2)
        except Exception:
            pass
    except Exception:
        pass

    # --- history-Call für Technicals ---
    try:
        import pandas as pd
        def _get_hist():
            return stock.history(period=f"{max(days, 2)}d")

        hist = _get_hist()

        if len(hist) >= 2:
            if not result.get("price"):
                result["price"] = round(float(hist["Close"].iloc[-1]), 2)
                prev = float(hist["Close"].iloc[-2])
                cur  = float(hist["Close"].iloc[-1])
                if prev:
                    result["change_pct"] = round(((cur - prev) / prev) * 100, 2)

        if len(hist) >= 5:
            c_now = float(hist["Close"].iloc[-1])
            c_5d  = float(hist["Close"].iloc[-5])
            if c_5d:
                result["change_5d_pct"] = round(((c_now - c_5d) / c_5d) * 100, 2)

        if len(hist) >= 15:
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
            result["atr_14"] = round(sum(tr[-14:]) / 14, 2) if len(tr) >= 14 else None

        if len(hist) >= 20:
            vol_today = float(hist["Volume"].iloc[-1])
            vol_avg20 = float(hist["Volume"].tail(20).mean())
            if vol_avg20 > 0:
                result["rvol"] = round(vol_today / vol_avg20, 2)

        if len(hist) >= 50:
            sma50 = float(hist["Close"].tail(50).mean())
            cur   = float(hist["Close"].iloc[-1])
            result["above_sma50"] = cur > sma50
    except Exception:
        pass

    # --- Earnings-Datum ---
    try:
        calendar = getattr(stock, "calendar", None)
        if calendar is not None:
            cal_data = calendar
            if hasattr(calendar, "to_dict"):
                cal_data = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in calendar.to_dict().items()}
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

    # iv_atm
    try:
        countdown = result.get("earnings_countdown")
        if countdown is not None and 0 <= countdown <= 14:
            opts = stock.options
            if opts and len(opts) > 0:
                chain = stock.option_chain(opts[0])
                atm_calls = chain.calls
                cur_price = result.get("price")
                if not atm_calls.empty and cur_price and cur_price > 0:
                    idx = ((atm_calls["strike"] - cur_price).abs().idxmin())
                    iv = float(atm_calls.loc[idx, "impliedVolatility"] or 0)
                    if iv > 0:
                        result["iv_atm"] = round(iv * 100, 1)
    except Exception:
        pass

    # report_timing
    try:
        calendar = getattr(stock, "calendar", None)
        if calendar is not None:
            cal_data = calendar
            if hasattr(calendar, "to_dict"):
                cal_data = {k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in calendar.to_dict().items()}
            if isinstance(cal_data, dict):
                timing_raw = cal_data.get("Earnings Call Time", "")
                if timing_raw:
                    t = str(timing_raw).lower()
                    if "before" in t or "pre" in t:
                        result["report_timing"] = "pre_market"
                    elif "after" in t or "post" in t:
                        result["report_timing"] = "after_market"
    except Exception:
        pass

    if result:
        cache_set(cache_key, result, ttl_seconds=300)

    entry.update(result)
    return entry

def _fetch_all_scores_sync(tickers: list, db) -> dict:
    """Lädt score_history für alle Ticker."""
    if not db or not tickers:
        return {}
    try:
        tickers_upper = list(dict.fromkeys(t.upper() for t in tickers if t))
        max_rows = len(tickers_upper) * 8
        res = db.table("score_history").select("*").in_("ticker", tickers_upper).order("date", desc=True).limit(max_rows).execute()
        rows = res.data if res and res.data else []

        by_ticker: dict = {}
        for row in rows:
            t = row.get("ticker", "").upper()
            if t not in by_ticker:
                by_ticker[t] = []
            by_ticker[t].append(row)

        for t in by_ticker:
            by_ticker[t].sort(key=lambda r: r.get("date") or "", reverse=True)
            by_ticker[t] = by_ticker[t][:7]

        # Fallback
        for ticker in tickers_upper:
            if len(by_ticker.get(ticker, [])) >= 7:
                continue
            try:
                single_res = db.table("score_history").select("*").eq("ticker", ticker).order("date", desc=True).limit(7).execute()
                single_rows = single_res.data if single_res and single_res.data else []
                if single_rows:
                    by_ticker[ticker] = single_rows[:7]
            except Exception:
                continue
        return by_ticker
    except Exception as e:
        logger.debug(f"_fetch_all_scores_sync error: {e}")
        return {}

async def _enrich_single(item: dict, scores_by_ticker: dict, bullets_by_ticker: dict | None = None, alpaca_prices: dict | None = None) -> dict:
    """Enriched einen einzelnen Watchlist-Ticker."""
    ticker = item.get("ticker")
    if not ticker:
        return item
    entry = dict(item)
    bullets_by_ticker = bullets_by_ticker or {}
    alpaca_prices = alpaca_prices or {}
    if "web_prio" not in entry:
        entry["web_prio"] = None

    # ── Preis aus Alpaca (primär, Batch bereits geladen) ─────────
    alpaca_snap = alpaca_prices.get(ticker.upper())
    if alpaca_snap and alpaca_snap.get("price"):
        entry["price"]          = alpaca_snap["price"]
        entry["change_pct"]     = alpaca_snap.get("change_pct")
        entry["prev_close"]     = alpaca_snap.get("prev_close")
        entry["bid"]            = alpaca_snap.get("bid")
        entry["ask"]            = alpaca_snap.get("ask")
        entry["volume_today"]   = alpaca_snap.get("volume")
        if alpaca_snap.get("bid") and alpaca_snap.get("ask"):
            spread = round(abs(alpaca_snap["ask"] - alpaca_snap["bid"]), 4)
            entry["bid_ask_spread"] = round(spread / alpaca_snap["price"] * 100, 4)
        _alpaca_used = True
    else:
        _alpaca_used = False
    # ── Ende Alpaca Preis ─────────────────────────────────────────

    # --- Kursdaten via fast_info (Fallback wenn Alpaca fehlt) ---
    if not _alpaca_used:
        try:
            entry = await asyncio.to_thread(_fetch_ticker_data_sync, ticker, entry)
        except Exception as exc:
            logger.debug(f"Enrich yfinance {ticker}: {exc}")
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
                entry["opp_delta"] = round((latest.get("opportunity_score") or 0) - (prev.get("opportunity_score") or 0), 1)
                entry["torp_delta"] = round((latest.get("torpedo_score") or 0) - (prev.get("torpedo_score") or 0), 1)
            if len(rows) >= 5:
                week_row = rows[min(4, len(rows)-1)]
                entry["week_opp_delta"] = round((latest.get("opportunity_score") or 0) - (week_row.get("opportunity_score") or 0), 1)
                entry["week_torp_delta"] = round((latest.get("torpedo_score") or 0) - (week_row.get("torpedo_score") or 0), 1)
    except Exception as exc:
        logger.debug(f"Enrich scores {ticker}: {exc}")
    try:
        ticker_bullets = bullets_by_ticker.get(ticker.upper(), [])
        if ticker_bullets:
            sent = _calc_sentiment_from_bullets(ticker_bullets)
            entry["finbert_sentiment"] = sent["avg"]
            entry["sentiment_label"] = sent["label"]
            entry["sentiment_trend"] = sent["trend"]
            entry["has_material_news"] = sent["has_material"]
            entry["sentiment_count"] = sent["count"]
    except Exception as exc:
        logger.debug(f"Sentiment enrich {ticker}: {exc}")
    return entry

@router.get("")
async def api_get_watchlist():
    logger.info("API Call: get-watchlist")
    return await get_watchlist()

@router.get("/enriched")
async def api_watchlist_enriched():
    """Gibt Watchlist inkl. Kurse, Scores und Earnings-Countdown zurück."""
    logger.info("API Call: watchlist-enriched")
    cache_key = "watchlist:enriched:v2"
    cached_result = cache_get(cache_key)
    if cached_result:
        return cached_result

    watchlist = await get_watchlist()
    db = get_supabase_client()
    tickers = list({item.get("ticker", "").upper() for item in watchlist if item.get("ticker")})
    
    # ── Alpaca Batch-Snapshot (1 Call für alle Ticker) ────────────
    alpaca_prices: dict[str, dict] = {}
    try:
        alpaca_prices = await alpaca_get_snapshots(tickers)
        if alpaca_prices:
            logger.info(
                f"Alpaca Batch-Snapshot: {len(alpaca_prices)}/{len(tickers)} Ticker geladen"
            )
    except Exception as e:
        logger.warning(f"Alpaca Batch-Snapshot fehlgeschlagen — Fallback auf yfinance: {e}")
    # ── Ende Batch-Snapshot ───────────────────────────────────────
    
    scores_by_ticker = await asyncio.to_thread(_fetch_all_scores_sync, tickers, db)
    bullets_by_ticker = await get_bullet_points_batch(tickers, limit_per_ticker=10)
    results = await asyncio.gather(*[_enrich_single(item, scores_by_ticker, bullets_by_ticker, alpaca_prices) for item in watchlist], return_exceptions=True)

    enriched = []
    sectors: dict[str, int] = {}
    for r in results:
        if isinstance(r, Exception):
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
            concentration_warning = f"⚠️ Klumpenrisiko: {concentration_pct:.0f}% der Watchlist ist im Sektor '{dominant_sector}'. Diversifikation prüfen."

    # ── Earnings Live-Modus: Cache-TTL anpassen ───────────────────
    has_earnings_today = any(
        entry.get("earnings_today") or entry.get("earnings_countdown") == 0
        for entry in enriched
    )
    cache_ttl = 10 if has_earnings_today else 300
    if has_earnings_today:
        logger.info("Earnings Live-Modus: Watchlist-Cache auf 10s reduziert")
    # ── Ende Earnings Live-Modus ───────────────────────────────────

    result = {"watchlist": enriched, "concentration_warning": concentration_warning, "sector_distribution": sectors}
    await cache_set(cache_key, result, ttl_seconds=cache_ttl)
    return result

@router.post("")
async def api_add_watchlist_item(item: WatchlistItemCreate, background_tasks: BackgroundTasks):
    logger.info(f"API Call: add-watchlist-item {item.ticker}")
    logger.info(f"Cross signals type: {type(item.cross_signals)}, value: {item.cross_signals}")
    company_name = item.company_name or item.ticker.upper()
    sector = item.sector or "Unknown"
    
    from backend.app.data.news_processor import process_news_for_ticker
    async def _scan_and_invalidate(ticker: str):
        await process_news_for_ticker(ticker)
        cache_invalidate("watchlist:enriched:v2")
        cache_invalidate(f"research_dashboard_{ticker}")
        cache_invalidate_prefix("earnings_radar_")

    background_tasks.add_task(_scan_and_invalidate, item.ticker.upper())
    cache_invalidate("watchlist:enriched:v2")
    
    # TODO: Fix cross_signals array handling - temporarily using empty array
    return await add_ticker(item.ticker, company_name, sector, item.notes or "", [])

@router.get("/earnings-this-week")
async def api_watchlist_earnings_this_week():
    logger.info("API Call: watchlist-earnings-this-week")
    from datetime import datetime, timedelta
    from backend.app.data.finnhub import get_earnings_calendar
    from backend.app.utils.timezone import now_mez
    now = now_mez()
    end_of_week = now + timedelta(days=7)
    cal = await get_earnings_calendar(now.strftime("%Y-%m-%d"), end_of_week.strftime("%Y-%m-%d"))
    wl = await get_watchlist()
    return await get_earnings_this_week(wl, cal)

@router.put("/{ticker}")
async def api_update_watchlist_item(ticker: str, item: WatchlistItemUpdate):
    logger.info(f"API Call: update-watchlist-item {ticker}")
    update_data = item.dict(exclude_unset=True) 
    try:
        db = get_supabase_client()
        if db and update_data:
            await db.table("watchlist").update(update_data).eq("ticker", ticker.upper()).execute_async()
        cache_invalidate("watchlist:enriched:v2")
        return {"status": "success", "updated": update_data}
    except Exception as e:
        logger.error(f"Watchlist Update Error für {ticker}: {e}")
        return {"status": "error", "message": str(e)}

@router.delete("/{ticker}")
async def api_remove_watchlist_item(ticker: str):
    logger.info(f"API Call: remove-watchlist-item {ticker}")
    cache_invalidate("watchlist:enriched:v2")
    success = await remove_ticker(ticker)
    return {"status": "success"} if success else {"status": "error"}
