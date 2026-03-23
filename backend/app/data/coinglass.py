"""
coinglass.py — CoinGlass API Datenabruf

Endpunkte: Open Interest, Funding Rate, Long/Short Ratio
CoinGlass Free Tier: 30 Requests/Min, täglich ausreichend
CoinGlass Pro (~30$/Mo): Liquidation Heatmap mit exakten Cluster-Levels

Dokumentation: https://coinglass.com/API3
"""
import httpx
import asyncio
from typing import Optional
from backend.app.config import settings
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

COINGLASS_BASE = "https://open-api.coinglass.com/public/v2"


async def _cg_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """CoinGlass GET mit API-Key. Gibt None zurück bei Fehler."""
    api_key = settings.coinglass_api_key
    if not api_key:
        logger.warning("COINGLASS_API_KEY nicht gesetzt")
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{COINGLASS_BASE}{endpoint}",
                params=params or {},
                headers={"coinglassSecret": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "0":
                logger.warning(f"CoinGlass API Fehler: {data.get('msg')}")
                return None
            return data.get("data")
    except Exception as e:
        logger.error(f"CoinGlass Fehler {endpoint}: {e}")
        return None


async def get_btc_open_interest() -> Optional[dict]:
    """Bitcoin Open Interest (gesamt, alle Exchanges)."""
    cache_key = "cg:btc:open_interest"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    data = await _cg_get("/indicator/open_interest", {"symbol": "BTC", "currency": "USD"})
    if data:
        result = {
            "total_oi_usd": data.get("oiUsd"),
            "change_24h_pct": data.get("h24Change"),
            "exchanges": data.get("exchangeList", [])[:5],
        }
        await cache_set(cache_key, result, ttl_seconds=1800)
        return result
    return None


async def get_btc_funding_rates() -> Optional[dict]:
    """Bitcoin Funding Rates — Durchschnitt und je Exchange."""
    cache_key = "cg:btc:funding"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    data = await _cg_get("/indicator/funding_rates_chart", {"symbol": "BTC"})
    if data:
        rates = data.get("dataMap", {})
        avg = None
        if rates:
            vals = [v for v in rates.values() if v is not None]
            avg = round(sum(vals) / len(vals) * 100, 4) if vals else None
        result = {
            "avg_funding_rate_pct": avg,
            "interpretation": (
                "Stark bullish (Longs zahlen hohe Prämie)" if avg and avg > 0.05
                else "Leicht bullish" if avg and avg > 0.01
                else "Neutral" if avg and abs(avg) <= 0.01
                else "Leicht bearish" if avg and avg > -0.05
                else "Stark bearish (Shorts zahlen Prämie)" if avg
                else "Keine Daten"
            ),
            "exchange_rates": rates,
        }
        await cache_set(cache_key, result, ttl_seconds=1800)
        return result
    return None


async def get_btc_long_short_ratio() -> Optional[dict]:
    """Bitcoin Long/Short Ratio (Retail-Sentiment)."""
    cache_key = "cg:btc:ls_ratio"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    data = await _cg_get("/indicator/global_long_short_account_ratio",
                          {"symbol": "BTC", "interval": "h1", "limit": 1})
    if data and isinstance(data, list) and data:
        latest = data[-1]
        result = {
            "long_pct":   round(float(latest.get("longRatio", 0.5)) * 100, 1),
            "short_pct":  round(float(latest.get("shortRatio", 0.5)) * 100, 1),
            "ratio":      round(float(latest.get("longShortRatio", 1.0)), 2),
        }
        await cache_set(cache_key, result, ttl_seconds=1800)
        return result
    return None


async def get_btc_liquidation_levels() -> Optional[dict]:
    """
    Bitcoin Liquidationscluster — nächste Long- und Short-Liquidationszonen.
    Erfordert CoinGlass Pro für detaillierte Heatmap.
    Free Tier: nur grobe Liquidations-Volumina.
    """
    cache_key = "cg:btc:liquidations"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    data = await _cg_get("/indicator/liquidation_heatmap",
                          {"symbol": "BTC", "range": "12h"})
    if data:
        result = {"raw": data, "available": True}
        await cache_set(cache_key, result, ttl_seconds=3600)
        return result
    # Free Tier Fallback: keine Daten verfügbar
    return {"available": False, "note": "CoinGlass Pro für Liquidations-Cluster erforderlich"}


async def get_btc_price_and_trend() -> dict:
    """BTC-USD Kurs und 7-Tage-Trend via yfinance (kein API-Key nötig)."""
    cache_key = "btc:price_trend"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    try:
        import yfinance as yf
        def _fetch():
            hist = yf.Ticker("BTC-USD").history(period="14d")
            if hist.empty:
                return {}
            current = float(hist["Close"].iloc[-1])
            price_7d_ago = float(hist["Close"].iloc[-7]) if len(hist) >= 7 else current
            change_7d = round((current - price_7d_ago) / price_7d_ago * 100, 2)
            high_14d  = float(hist["High"].max())
            low_14d   = float(hist["Low"].min())
            return {
                "price":      round(current, 0),
                "change_7d_pct": change_7d,
                "high_14d":   round(high_14d, 0),
                "low_14d":    round(low_14d, 0),
                "trend":      "bullish" if change_7d > 3 else "bearish" if change_7d < -3 else "sideways",
            }
        result = await asyncio.to_thread(_fetch)
        if result:
            await cache_set(cache_key, result, ttl_seconds=900)  # 15 Min
        return result or {}
    except Exception as e:
        logger.error(f"BTC price fetch: {e}")
        return {}


async def get_full_btc_snapshot() -> dict:
    """Vollständiger BTC-Snapshot: Preis + OI + Funding + L/S + Liq."""
    price, oi, funding, ls_ratio, liq = await asyncio.gather(
        get_btc_price_and_trend(),
        get_btc_open_interest(),
        get_btc_funding_rates(),
        get_btc_long_short_ratio(),
        get_btc_liquidation_levels(),
        return_exceptions=True,
    )
    return {
        "price":           price if not isinstance(price, Exception) else {},
        "open_interest":   oi if not isinstance(oi, Exception) else None,
        "funding_rate":    funding if not isinstance(funding, Exception) else None,
        "long_short":      ls_ratio if not isinstance(ls_ratio, Exception) else None,
        "liquidations":    liq if not isinstance(liq, Exception) else None,
    }
