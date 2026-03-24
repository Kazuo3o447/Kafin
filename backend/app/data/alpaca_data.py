"""
alpaca_data.py — Alpaca Market Data API Client

Endpunkte:
  /v2/stocks/snapshots  — Batch-Preis für mehrere Ticker (1 Call)
  /v2/stocks/{t}/bars   — OHLCV Bars (für Sparkline)
  /v2/stocks/{t}/quotes/latest — Aktueller Bid/Ask

Base-URL: https://data.alpaca.markets (NICHT paper-api!)
Auth:     Dieselben Keys wie Trading API

Einschränkungen Free Tier:
  - IEX-Daten (15-Min-Delay für US-Aktien)
  - Kein Options-Flow, kein Short Interest, keine Fundamentals
  - Nur US-Aktien (kein DAX, Nikkei etc.)

Architektur-Entscheidung:
  Ersetzt yfinance NUR für Preisdaten (price, change%, bid/ask, RVOL).
  yfinance bleibt für: Options, Fundamentals, ATR/MACD-Berechnung.

Dokumentation: https://docs.alpaca.markets/docs/about-market-data-api
"""
import httpx
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from backend.app.config import settings
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

_CACHE_TTL_PRICE   = 60    # 1 Min — Preis-Snapshots
_CACHE_TTL_BARS    = 300   # 5 Min — OHLCV Bars
_CACHE_TTL_QUOTE   = 30    # 30s — Bid/Ask


def _configured() -> bool:
    """True wenn Alpaca-Keys gesetzt sind."""
    return bool(settings.alpaca_api_key and settings.alpaca_secret_key)


def _data_headers() -> dict:
    return {
        "APCA-API-KEY-ID":     settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        "Accept":              "application/json",
    }


def _data_url(path: str) -> str:
    base = settings.alpaca_data_url.rstrip("/")
    return f"{base}{path}"


async def _get(path: str, params: dict = None) -> Optional[dict]:
    """
    Alpaca Data API GET. Gibt None bei Fehler zurück.
    Niemals Exception nach oben — yfinance ist Fallback.
    """
    if not _configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                _data_url(path),
                headers=_data_headers(),
                params=params or {},
            )
            if resp.status_code == 429:
                logger.warning("Alpaca Data: Rate Limit — Fallback auf yfinance")
                return None
            if resp.status_code == 403:
                logger.warning(
                    "Alpaca Data: 403 Forbidden — Market Data Scope prüfen "
                    "(app.alpaca.markets → API Keys → Edit → Market Data aktivieren)"
                )
                return None
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        logger.warning(f"Alpaca Data: Timeout für {path}")
        return None
    except Exception as e:
        logger.error(f"Alpaca Data Fehler {path}: {e}")
        return None


async def get_snapshots(tickers: list[str]) -> dict[str, dict]:
    """
    Batch-Snapshot für mehrere Ticker in EINEM API-Call.

    Gibt zurück: {
      "AAPL": {
        "price": 195.50,
        "change_pct": 1.23,
        "prev_close": 193.10,
        "bid": 195.48,
        "ask": 195.52,
        "volume": 45234123,
        "rvol": 1.23,        # Volumen heute / Durchschnitt 20T (approximiert)
        "high": 196.20,
        "low": 194.80,
        "vwap": 195.10,
      },
      ...
    }
    """
    if not tickers:
        return {}

    tickers_upper = [t.upper() for t in tickers if t]
    cache_key = f"alpaca:snapshots:{','.join(sorted(tickers_upper))}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _get(
        "/v2/stocks/snapshots",
        {"symbols": ",".join(tickers_upper), "feed": "iex"},
    )
    if not data:
        return {}

    result: dict[str, dict] = {}
    for ticker, snap in data.items():
        try:
            daily    = snap.get("dailyBar") or {}
            prev     = snap.get("prevDailyBar") or {}
            quote    = snap.get("latestQuote") or {}
            trade    = snap.get("latestTrade") or {}

            price    = float(trade.get("p") or daily.get("c") or 0)
            prev_cls = float(prev.get("c") or 0)
            chg_pct  = round(((price - prev_cls) / prev_cls) * 100, 2) if prev_cls else None
            vol_today = float(daily.get("v") or 0)

            result[ticker] = {
                "price":      round(price, 4) if price else None,
                "change_pct": chg_pct,
                "prev_close": round(prev_cls, 4) if prev_cls else None,
                "bid":        float(quote.get("bp") or 0) or None,
                "ask":        float(quote.get("ap") or 0) or None,
                "volume":     int(vol_today) if vol_today else None,
                "high":       float(daily.get("h") or 0) or None,
                "low":        float(daily.get("l") or 0) or None,
                "open":       float(daily.get("o") or 0) or None,
                "vwap":       float(daily.get("vw") or 0) or None,
            }
        except Exception as e:
            logger.debug(f"Alpaca snapshot parse {ticker}: {e}")

    if result:
        await cache_set(cache_key, result, ttl_seconds=_CACHE_TTL_PRICE)
    return result


async def get_snapshot(ticker: str) -> Optional[dict]:
    """Einzelner Snapshot — nutzt intern den Batch-Call."""
    snaps = await get_snapshots([ticker])
    return snaps.get(ticker.upper())


async def get_bars(
    ticker: str,
    days: int = 7,
    timeframe: str = "1Day",
) -> list[dict]:
    """
    OHLCV Bars für Sparkline und OHLCV-Endpunkt.

    timeframe: "1Min" | "5Min" | "1Hour" | "1Day"
    Gibt zurück: [{"date": "2026-03-20", "open": ..., "high": ...,
                   "low": ..., "close": ..., "volume": ...}]
    """
    cache_key = f"alpaca:bars:{ticker.upper()}:{days}:{timeframe}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    start = (datetime.now(timezone.utc) - timedelta(days=days + 5)).strftime("%Y-%m-%d")
    data = await _get(
        f"/v2/stocks/{ticker.upper()}/bars",
        {
            "timeframe": timeframe,
            "start":     start,
            "feed":      "iex",
            "limit":     days + 5,
        },
    )
    if not data:
        return []

    bars = data.get("bars") or []
    result = []
    for bar in bars:
        t = bar.get("t", "")
        result.append({
            "date":   t[:10] if t else "",
            "open":   round(float(bar.get("o", 0)), 4),
            "high":   round(float(bar.get("h", 0)), 4),
            "low":    round(float(bar.get("l", 0)), 4),
            "close":  round(float(bar.get("c", 0)), 4),
            "volume": int(bar.get("v", 0)),
            "vwap":   round(float(bar.get("vw", 0)), 4) if bar.get("vw") else None,
        })

    result = result[-days:]
    if result:
        await cache_set(cache_key, result, ttl_seconds=_CACHE_TTL_BARS)
    return result


async def get_latest_quote(ticker: str) -> Optional[dict]:
    """Aktueller Bid/Ask für Research-Page."""
    cache_key = f"alpaca:quote:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _get(f"/v2/stocks/{ticker.upper()}/quotes/latest",
                      {"feed": "iex"})
    if not data:
        return None

    q = data.get("quote") or {}
    result = {
        "bid":       float(q.get("bp") or 0) or None,
        "ask":       float(q.get("ap") or 0) or None,
        "bid_size":  int(q.get("bs") or 0) or None,
        "ask_size":  int(q.get("as") or 0) or None,
        "spread":    round(abs(
                         float(q.get("ap") or 0) - float(q.get("bp") or 0)
                     ), 4) if q.get("ap") and q.get("bp") else None,
    }
    if result.get("bid"):
        await cache_set(cache_key, result, ttl_seconds=_CACHE_TTL_QUOTE)
    return result


async def test_connection() -> dict:
    """Verbindungstest für Systemdiagnostik — SPY Snapshot."""
    if not _configured():
        return {
            "status":  "warning",
            "details": "ALPACA_API_KEY nicht gesetzt",
        }
    import time
    t0 = time.time()
    snap = await get_snapshot("SPY")
    ms = round((time.time() - t0) * 1000)

    if snap and snap.get("price"):
        return {
            "status":     "ok",
            "latency_ms": ms,
            "details": (
                f"SPY ${snap['price']} "
                f"({'+' if (snap.get('change_pct') or 0) >= 0 else ''}"
                f"{snap.get('change_pct', 0):.2f}%) · IEX-Feed"
            ),
        }
    if snap is None:
        return {
            "status":  "warning",
            "details": "Keine Daten — Market Data Scope in Alpaca-Keys prüfen",
        }
    return {
        "status":     "error",
        "latency_ms": ms,
        "details":    "Snapshot leer — Feed oder Key prüfen",
    }


async def get_asset_info(ticker: str) -> Optional[dict]:
    """
    Alpaca Asset-Info: shortbar, easy_to_borrow, tradeable.
    Wichtig vor Short-Signalen — manche Titel sind Hard to Borrow (HTB).

    Gibt zurück: {
        "shortable":       bool,
        "easy_to_borrow":  bool,
        "tradeable":       bool,
        "status":          str,  # "active" | "inactive"
    }
    """
    cache_key = f"alpaca:asset:{ticker.upper()}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await _get(f"/v2/assets/{ticker.upper()}")
    if not data:
        return None

    result = {
        "shortable":      bool(data.get("shortable", False)),
        "easy_to_borrow": bool(data.get("easy_to_borrow", False)),
        "tradeable":      bool(data.get("tradeable", True)),
        "status":         data.get("status", "unknown"),
    }
    # Asset-Info ändert sich selten — 6h Cache
    await cache_set(cache_key, result, ttl_seconds=21600)
    return result
