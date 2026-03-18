"""
cache — Redis-basierter Cache für API-Daten

Input:  Key, Value, TTL
Output: Gecachte Daten oder None
Deps:   redis, config.py
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis

from backend.app.logger import get_logger

logger = get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://kafin-redis:6379/0")

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            _redis_client.ping()
            logger.info("Redis Cache verbunden.")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"Redis nicht verfügbar: {exc}")
            _redis_client = None
    return _redis_client


def cache_get(key: str) -> Any:
    """Holt einen Wert aus dem Cache. None wenn leer oder Redis fehlt."""
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(key)
        if raw is not None:
            return json.loads(raw)
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Cache get Fehler für {key}: {exc}")
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:  # pragma: no cover
        logger.debug(f"Cache set Fehler für {key}: {exc}")
