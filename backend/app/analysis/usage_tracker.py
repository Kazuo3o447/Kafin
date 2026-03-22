"""
API Usage Tracker — zählt Calls und Tokens.

Schreibt täglich aggregiert in api_usage Tabelle.
Nutzt Redis als schnellen In-Memory-Puffer,
flusht in DB alle 5 Minuten oder bei Abfrage.
"""
import asyncio
from datetime import date
from typing import Optional
from backend.app.cache import cache_get, cache_set
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Kosten pro 1M Tokens (USD) — Stand März 2026
PRICING = {
    "deepseek-chat": {
        "input":  0.28,   # cache miss
        "output": 0.42,
    },
    "deepseek-reasoner": {
        "input":  0.28,
        "output": 0.42,
    },
    "llama-3.1-8b-instant": {
        "input":  0.0,    # Groq Free Tier
        "output": 0.0,
    },
    "llama-3.3-70b-versatile": {
        "input":  0.0,
        "output": 0.0,
    },
}

def _redis_key(api: str, model: Optional[str] = None) -> str:
    today = date.today().isoformat()
    m = f":{model}" if model else ""
    return f"usage:{today}:{api}{m}"


def track_call(
    api_name: str,
    model: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> None:
    """
    Registriert einen API-Call im Redis-Puffer.
    Synchron — kann überall aufgerufen werden.
    Kein await nötig.
    """
    try:
        key = _redis_key(api_name, model)
        existing = cache_get(key) or {
            "call_count":     0,
            "input_tokens":   0,
            "output_tokens":  0,
            "total_tokens":   0,
            "cost_usd":       0.0,
            "api_name":       api_name,
            "model":          model,
            "date":           date.today().isoformat(),
        }

        existing["call_count"]   += 1
        existing["input_tokens"] += input_tokens
        existing["output_tokens"] += output_tokens
        existing["total_tokens"] += (
            input_tokens + output_tokens
        )

        # Kosten berechnen
        pricing = PRICING.get(model or "", {})
        cost = (
            input_tokens  / 1_000_000
            * pricing.get("input", 0)
            + output_tokens / 1_000_000
            * pricing.get("output", 0)
        )
        existing["cost_usd"] = round(
            existing["cost_usd"] + cost, 6
        )

        # 25h TTL (Tagesgrenze + Puffer)
        cache_set(key, existing, ttl_seconds=90000)

    except Exception as e:
        logger.debug(f"Usage tracking Fehler: {e}")


async def flush_to_db() -> None:
    """
    Schreibt Redis-Puffer in PostgreSQL.
    Wird alle 5 Minuten und beim /usage Endpoint aufgerufen.
    """
    try:
        from backend.app.database import get_pool
        pool = await get_pool()

        # Hole alle usage:* Keys aus Redis
        from backend.app.cache import _get_redis
        client = _get_redis()
        if not client:
            return

        today = date.today().isoformat()
        keys = client.keys(f"usage:{today}:*")

        for key in keys:
            data = cache_get(key)
            if not data:
                continue

            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO api_usage
                        (date, api_name, model,
                         call_count, input_tokens,
                         output_tokens, total_tokens,
                         estimated_cost_usd, updated_at)
                    VALUES
                        ($1, $2, $3, $4, $5, $6, $7, $8,
                         NOW())
                    ON CONFLICT (date, api_name, model)
                    DO UPDATE SET
                        call_count      = EXCLUDED.call_count,
                        input_tokens    = EXCLUDED.input_tokens,
                        output_tokens   = EXCLUDED.output_tokens,
                        total_tokens    = EXCLUDED.total_tokens,
                        estimated_cost_usd =
                            EXCLUDED.estimated_cost_usd,
                        updated_at      = NOW()
                """,
                    today,
                    data["api_name"],
                    data.get("model"),
                    data["call_count"],
                    data["input_tokens"],
                    data["output_tokens"],
                    data["total_tokens"],
                    data["cost_usd"],
                )
    except Exception as e:
        logger.debug(f"Usage flush Fehler: {e}")


async def get_usage_summary(days: int = 7) -> list[dict]:
    """
    Holt aggregierte Usage-Daten der letzten N Tage.
    Erst flush, dann aus DB lesen.
    """
    await flush_to_db()

    try:
        from backend.app.database import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    date,
                    api_name,
                    model,
                    call_count,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    estimated_cost_usd
                FROM api_usage
                WHERE date >= CURRENT_DATE - $1
                ORDER BY date DESC, api_name, model
            """, days)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Usage query Fehler: {e}")
        return []


async def get_today_summary() -> dict:
    """
    Holt heutigen Usage direkt aus Redis (schnell).
    Kein DB-Roundtrip.
    """
    from backend.app.cache import _get_redis
    client = _get_redis()
    if not client:
        return {}

    today = date.today().isoformat()
    keys = client.keys(f"usage:{today}:*")

    result: dict[str, dict] = {}
    for key in keys:
        data = cache_get(key)
        if not data:
            continue
        api = data["api_name"]
        model = data.get("model") or "default"
        if api not in result:
            result[api] = {}
        result[api][model] = {
            "calls":       data["call_count"],
            "input_tokens":  data["input_tokens"],
            "output_tokens": data["output_tokens"],
            "total_tokens":  data["total_tokens"],
            "cost_usd":    data["cost_usd"],
        }
    return result
