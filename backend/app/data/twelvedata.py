"""
twelvedata.py — Twelve Data API Client

Endpunkte: ADX, Stochastic, technische Indikatoren
Free Tier: 800 Calls/Tag, 8/Min
Cache: 4 Stunden (Indikatoren ändern sich tagesweise)

Architektonisches Prinzip: TD ERGÄNZT yfinance, ersetzt es nicht.
Nur für Indikatoren die yfinance nicht zuverlässig liefert:
- ADX (Average Directional Index) — Trendstärke
- Stochastic Oscillator — Momentum-Confirmation
- IV-Approximation via Historical Volatility Ratio

API-Dokumentation: https://twelvedata.com/docs
"""
import httpx
import asyncio
from typing import Optional
from backend.app.config import settings
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

_TD_BASE = "https://api.twelvedata.com"
_CACHE_TTL = 14400  # 4 Stunden


def _configured() -> bool:
    return bool(settings.twelve_data_api_key)


async def _td_get(endpoint: str, params: dict) -> Optional[dict]:
    """
    Twelve Data GET. Gibt None bei Fehler oder fehlendem Key zurück.
    Loggt Warnungen aber wirft keine Exceptions nach oben.
    """
    if not _configured():
        return None
    params["apikey"] = settings.twelve_data_api_key
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(f"{_TD_BASE}{endpoint}", params=params)
            resp.raise_for_status()
            data = resp.json()
            # Twelve Data gibt {"status": "error", "message": "..."} bei Fehlern
            if data.get("status") == "error":
                logger.warning(
                    f"Twelve Data API Fehler ({endpoint}): {data.get('message')}"
                )
                return None
            return data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            logger.warning("Twelve Data: Rate Limit erreicht (8/Min)")
        else:
            logger.error(f"Twelve Data HTTP Fehler {endpoint}: {e}")
        return None
    except Exception as e:
        logger.error(f"Twelve Data Fehler {endpoint}: {e}")
        return None


async def get_adx(ticker: str, period: int = 14) -> Optional[dict]:
    """
    Average Directional Index (ADX) — misst Trendstärke (nicht Richtung).

    Interpretation:
    - ADX < 15: kein klarer Trend (sideways)
    - ADX 15–25: beginnender Trend
    - ADX 25–40: starker Trend (konfirmiert)
    - ADX > 40: sehr starker Trend (Breakout oder Exhaustion möglich)

    Gibt zurück: {"adx": float, "plus_di": float, "minus_di": float}
    """
    cache_key = f"td:adx:{ticker.upper()}:{period}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _td_get("/adx", {
        "symbol":      ticker.upper(),
        "interval":    "1day",
        "time_period": period,
        "outputsize":  1,
        "format":      "JSON",
    })
    if not data or "values" not in data:
        return None

    values = data.get("values", [])
    if not values:
        return None

    latest = values[0]
    result = {
        "adx":      round(float(latest.get("adx", 0)), 2),
        "plus_di":  round(float(latest.get("plus_di", 0)), 2),
        "minus_di": round(float(latest.get("minus_di", 0)), 2),
        "trend_strength": (
            "strong"    if float(latest.get("adx", 0)) >= 25 else
            "moderate"  if float(latest.get("adx", 0)) >= 15 else
            "weak"
        ),
    }
    await cache_set(cache_key, result, ttl_seconds=_CACHE_TTL)
    logger.debug(f"TD ADX {ticker}: {result['adx']} ({result['trend_strength']})")
    return result


async def get_stochastic(
    ticker: str,
    fast_k: int = 14,
    slow_k: int = 3,
    slow_d: int = 3,
) -> Optional[dict]:
    """
    Stochastic Oscillator — Position des Kurses im Preis-Range.

    Interpretation:
    - %K < 20: überverkauft (Bounce möglich)
    - %K > 80: überkauft (Reversal möglich)
    - %K kreuzt %D von unten: bullisches Signal
    - %K kreuzt %D von oben: bärisches Signal

    Gibt zurück: {"slow_k": float, "slow_d": float, "signal": str}
    """
    cache_key = f"td:stoch:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _td_get("/stoch", {
        "symbol":    ticker.upper(),
        "interval":  "1day",
        "fast_k_period": fast_k,
        "slow_k_period": slow_k,
        "slow_d_period": slow_d,
        "outputsize": 2,   # 2 Werte für Kreuzungserkennung
        "format":    "JSON",
    })
    if not data or "values" not in data:
        return None

    values = data.get("values", [])
    if len(values) < 1:
        return None

    latest = values[0]
    prev   = values[1] if len(values) > 1 else None

    slow_k_val = float(latest.get("slow_k", 50))
    slow_d_val = float(latest.get("slow_d", 50))

    # Kreuzungs-Signal
    signal = "neutral"
    if prev:
        prev_k = float(prev.get("slow_k", 50))
        prev_d = float(prev.get("slow_d", 50))
        if prev_k <= prev_d and slow_k_val > slow_d_val:
            signal = "bullish_cross"
        elif prev_k >= prev_d and slow_k_val < slow_d_val:
            signal = "bearish_cross"
        elif slow_k_val < 20:
            signal = "oversold"
        elif slow_k_val > 80:
            signal = "overbought"

    result = {
        "slow_k":  round(slow_k_val, 2),
        "slow_d":  round(slow_d_val, 2),
        "signal":  signal,
    }
    await cache_set(cache_key, result, ttl_seconds=_CACHE_TTL)
    logger.debug(f"TD Stoch {ticker}: K={result['slow_k']} D={result['slow_d']} → {signal}")
    return result


async def get_td_technicals(ticker: str) -> dict:
    """
    Kombinierter Abruf: ADX + Stochastic parallel.
    Gibt immer ein Dict zurück — einzelne Felder können None sein
    wenn TD nicht konfiguriert oder Fehler aufgetreten ist.
    """
    if not _configured():
        return {"adx": None, "stochastic": None, "source": "not_configured"}

    adx, stoch = await asyncio.gather(
        get_adx(ticker),
        get_stochastic(ticker),
        return_exceptions=True,
    )

    return {
        "adx":        adx  if not isinstance(adx, Exception)   else None,
        "stochastic": stoch if not isinstance(stoch, Exception) else None,
        "source":     "twelve_data",
    }


async def test_connection() -> dict:
    """
    Verbindungstest für Systemdiagnostik.
    Ruft einen einzelnen ADX-Wert für SPY ab.
    """
    if not _configured():
        return {
            "status":  "warning",
            "details": "TWELVE_DATA_API_KEY nicht gesetzt",
        }
    import time
    t0 = time.time()
    result = await get_adx("SPY", period=14)
    ms = round((time.time() - t0) * 1000)

    if result:
        return {
            "status":     "ok",
            "latency_ms": ms,
            "details":    f"ADX(SPY)={result['adx']} · {result['trend_strength']}",
        }
    return {
        "status":     "error",
        "latency_ms": ms,
        "details":    "ADX-Abfrage fehlgeschlagen — Key oder Rate-Limit prüfen",
    }
