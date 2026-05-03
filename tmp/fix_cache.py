import shutil, os

src = "backend/app/cache.py"
shutil.copy(src, src + ".bak")

new_content = '''"""
cache — Async Redis Cache für API-Daten
"""
from __future__ import annotations
import json
import os
from typing import Any
import redis.asyncio as redis
from backend.app.logger import get_logger

logger = get_logger(__name__)
REDIS_URL = os.getenv("REDIS_URL", "redis://kafin-redis:6379/0")
_redis_client: redis.Redis | None = None


async def _get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            await _redis_client.ping()
            logger.info("Redis Cache verbunden.")
        except Exception as exc:
            logger.warning(f"Redis nicht verfügbar: {exc}")
            _redis_client = None
    return _redis_client


async def cache_get(key: str) -> Any:
    client = await _get_redis()
    if client is None:
        return None
    try:
        raw = await client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:
        logger.debug(f"Cache get Fehler für {key}: {exc}")
    return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    client = await _get_redis()
    if client is None:
        return
    try:
        await client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:
        logger.debug(f"Cache set Fehler für {key}: {exc}")


async def cache_invalidate(key: str) -> bool:
    client = await _get_redis()
    if client is None:
        return False
    try:
        await client.delete(key)
        return True
    except Exception as exc:
        logger.debug(f"Cache invalidate Fehler für {key}: {exc}")
        return False


async def cache_invalidate_prefix(prefix: str) -> int:
    client = await _get_redis()
    if client is None:
        return 0
    deleted = 0
    try:
        async for key in client.scan_iter(match=f"{prefix}*"):
            deleted += await client.delete(key)
        return deleted
    except Exception as exc:
        logger.debug(f"Cache invalidate prefix Fehler für {prefix}: {exc}")
        return deleted
'''

with open(src, "w") as f:
    f.write(new_content)

print(f"✅ cache.py ersetzt ({len(new_content)} Zeichen)")
