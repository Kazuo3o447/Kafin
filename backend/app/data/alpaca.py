"""
alpaca.py — Alpaca Paper Trading Client

Endpunkte: Account, Orders, Positions
Basis-URL:  https://paper-api.alpaca.markets (Paper Trading)
Auth:       APCA-API-KEY-ID + APCA-API-SECRET-KEY Headers

Dokumentation: https://docs.alpaca.markets/docs/trading-api
"""
import httpx
from typing import Optional
from backend.app.config import settings
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID":     settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
        "Content-Type":        "application/json",
    }


def _configured() -> bool:
    return bool(settings.alpaca_api_key and settings.alpaca_secret_key)


async def get_alpaca_account() -> Optional[dict]:
    """Account-Info: Equity, Cash, Buying Power."""
    if not _configured():
        return None
    cache_key = "alpaca:account"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.alpaca_base_url}/v2/account",
                headers=_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            result = {
                "equity":        float(data.get("equity", 0)),
                "cash":          float(data.get("cash", 0)),
                "buying_power":  float(data.get("buying_power", 0)),
                "pnl_today":     float(data.get("unrealized_pl", 0)),
                "status":        data.get("status"),
                "currency":      data.get("currency", "USD"),
            }
            await cache_set(cache_key, result, ttl_seconds=60)
            return result
    except Exception as e:
        logger.error(f"Alpaca account: {e}")
        return None


async def get_alpaca_positions() -> list[dict]:
    """Alle offenen Paper-Trading-Positionen."""
    if not _configured():
        return []
    cache_key = "alpaca:positions"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.alpaca_base_url}/v2/positions",
                headers=_headers(),
            )
            resp.raise_for_status()
            positions = resp.json()
            result = [
                {
                    "ticker":         p.get("symbol"),
                    "qty":            float(p.get("qty", 0)),
                    "side":           p.get("side"),           # "long" / "short"
                    "entry_price":    float(p.get("avg_entry_price", 0)),
                    "current_price":  float(p.get("current_price", 0)),
                    "market_value":   float(p.get("market_value", 0)),
                    "unrealized_pnl": float(p.get("unrealized_pl", 0)),
                    "unrealized_pct": float(p.get("unrealized_plpc", 0)) * 100,
                }
                for p in positions
            ]
            await cache_set(cache_key, result, ttl_seconds=60)
            return result
    except Exception as e:
        logger.error(f"Alpaca positions: {e}")
        return []


async def place_market_order(
    ticker: str,
    qty: float,
    side: str,               # "buy" | "sell"
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    client_order_id: Optional[str] = None,
) -> dict:
    """
    Market Order platzieren. Optionaler Stop-Loss und Take-Profit
    werden als separate Orders angelegt.
    Gibt Order-ID zurück oder Fehler-Dict.
    """
    if not _configured():
        return {"error": "Alpaca nicht konfiguriert"}
    if qty <= 0:
        return {"error": f"Ungültige Quantity: {qty}"}
    if side not in ("buy", "sell"):
        return {"error": f"Ungültige Side: {side}"}

    payload: dict = {
        "symbol":        ticker.upper(),
        "qty":           str(round(qty, 4)),
        "side":          side,
        "type":          "market",
        "time_in_force": "day",
    }
    if client_order_id:
        payload["client_order_id"] = client_order_id[:48]

    # Bracket Order wenn Stop und/oder Target angegeben
    if stop_loss or take_profit:
        payload["order_class"] = "bracket" if (stop_loss and take_profit) else "oto"
        payload["type"] = "market"
        if stop_loss:
            payload["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
        if take_profit:
            payload["take_profit"] = {"limit_price": str(round(take_profit, 2))}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.alpaca_base_url}/v2/orders",
                headers=_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "success":        True,
                "order_id":       data.get("id"),
                "client_order_id":data.get("client_order_id"),
                "status":         data.get("status"),
                "ticker":         data.get("symbol"),
                "qty":            data.get("qty"),
                "side":           data.get("side"),
            }
    except httpx.HTTPStatusError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            pass
        logger.error(f"Alpaca order error {ticker}: {e.response.status_code} {body}")
        return {"error": body.get("message", str(e))}
    except Exception as e:
        logger.error(f"Alpaca order exception {ticker}: {e}")
        return {"error": str(e)}


async def close_position(ticker: str) -> dict:
    """Position schließen (Market Order Gegenrichtung)."""
    if not _configured():
        return {"error": "Alpaca nicht konfiguriert"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{settings.alpaca_base_url}/v2/positions/{ticker.upper()}",
                headers=_headers(),
            )
            resp.raise_for_status()
            return {"success": True, "ticker": ticker}
    except Exception as e:
        logger.error(f"Alpaca close {ticker}: {e}")
        return {"error": str(e)}


async def get_alpaca_orders(status: str = "open") -> list[dict]:
    """Orders abrufen (open / closed / all)."""
    if not _configured():
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.alpaca_base_url}/v2/orders",
                headers=_headers(),
                params={"status": status, "limit": 50},
            )
            resp.raise_for_status()
            orders = resp.json()
            return [
                {
                    "order_id":   o.get("id"),
                    "ticker":     o.get("symbol"),
                    "side":       o.get("side"),
                    "qty":        o.get("qty"),
                    "status":     o.get("status"),
                    "filled_avg": o.get("filled_avg_price"),
                    "created_at": o.get("created_at"),
                }
                for o in orders
            ]
    except Exception as e:
        logger.error(f"Alpaca orders: {e}")
        return []
