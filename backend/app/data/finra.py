"""
FINRA Reg SHO Daily Short Sale Volume.
Kostenlos, kein API-Key.
Ergänzt FMP Short Interest (bi-wöchentlich) mit
täglichen Daten.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import httpx

from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

FINRA_BASE = (
    "https://cdn.finra.org/equity/regsho/daily/"
    "CNMSshvol{date}.txt"
)


async def get_finra_short_volume(
    ticker: str
) -> dict:
    """
    Holt FINRA Short Volume für einen Ticker.
    Sucht in den letzten 5 Handelstagen.
    Gibt Short Volume Ratio zurück (0.0-1.0).
    """
    cache_key = f"finra:sv:{ticker.upper()}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    def _fetch_day(date_str: str) -> Optional[dict]:
        url = FINRA_BASE.format(date=date_str)
        try:
            import httpx as _httpx
            resp = _httpx.get(url, timeout=10.0)
            if resp.status_code != 200:
                return None
            lines = resp.text.strip().split("\n")
            # Format: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market
            for line in lines[1:]:  # Skip header
                parts = line.split("|")
                if len(parts) >= 5 and parts[1].upper() == ticker.upper():
                    short_vol = int(parts[2]) if parts[2].isdigit() else 0
                    total_vol = int(parts[4]) if parts[4].isdigit() else 0
                    if total_vol > 0:
                        return {
                            "date": date_str,
                            "short_volume": short_vol,
                            "total_volume": total_vol,
                            "short_volume_ratio": round(
                                short_vol / total_vol, 3
                            ),
                        }
        except Exception as e:
            logger.debug(f"FINRA fetch {date_str}: {e}")
        return None

    def _find_latest():
        # Suche letzte 5 Handelstage
        today = datetime.now()
        for days_back in range(1, 8):
            d = today - timedelta(days=days_back)
            if d.weekday() < 5:  # Kein Weekend
                date_str = d.strftime("%Y%m%d")
                result = _fetch_day(date_str)
                if result:
                    return result
        return None

    try:
        data = await asyncio.to_thread(_find_latest)
        result = data or {
            "short_volume_ratio": None,
            "error": "Keine FINRA-Daten",
        }
        result["ticker"] = ticker.upper()
        cache_set(cache_key, result, ttl_seconds=86400)  # 24h
        return result
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e)}


async def get_squeeze_signal(
    ticker: str,
    short_interest_pct: Optional[float] = None,
) -> dict:
    """
    Kombiniert FINRA Short Volume + FMP Short Interest
    zu einem Squeeze-Signal.
    """
    finra = await get_finra_short_volume(ticker)
    sv_ratio = finra.get("short_volume_ratio")

    signal = "neutral"
    score = 0.0

    # FINRA Short Volume Ratio
    if sv_ratio is not None:
        if sv_ratio > 0.55:    # >55% Short Volume
            score += 2.0
        elif sv_ratio > 0.45:
            score += 1.0

    # FMP/yfinance Short Interest
    if short_interest_pct is not None:
        if short_interest_pct > 15:  # >15% Float short
            score += 2.0
        elif short_interest_pct > 8:
            score += 1.0

    if score >= 3.0:
        signal = "high_squeeze_risk"
    elif score >= 1.5:
        signal = "elevated"

    return {
        "ticker": ticker.upper(),
        "signal": signal,
        "score": score,
        "short_volume_ratio": sv_ratio,
        "short_volume_date": finra.get("date"),
        "short_interest_pct": short_interest_pct,
    }
