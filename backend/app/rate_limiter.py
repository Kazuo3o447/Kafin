"""
rate_limiter — Zentraler Rate-Limiter für alle externen APIs

Input:  API Name und Request Parameter
Output: Steuert das Timing der Requests
Deps:   config, redis
Config: apis.yaml (Rate Limits)
API:    Keine
"""
import time
import asyncio
from functools import wraps
from typing import Callable, Any
import os
import redis.asyncio as redis
from backend.app.config import settings, load_yaml_config
from backend.app.logger import get_logger

logger = get_logger(__name__)

APIS_YAML = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "apis.yaml")
_limits = {}
try:
    _limits = load_yaml_config(APIS_YAML)
except Exception as e:
    logger.error(f"Could not load apis.yaml: {e}")

class RateLimiter:
    def __init__(self):
        self._local_locks = {}
        self._local_counts = {}

    async def wait_for_capacity(self, api_name: str):
        limit = _limits.get(api_name, {}).get("rate_limit", 10)
        
        if api_name not in self._local_locks:
            self._local_locks[api_name] = asyncio.Lock()
            self._local_counts[api_name] = []
            
        async with self._local_locks[api_name]:
            now = time.time()
            self._local_counts[api_name] = [t for t in self._local_counts[api_name] if now - t < 1.0]
            
            if len(self._local_counts[api_name]) >= limit:
                sleep_time = 1.0 - (now - self._local_counts[api_name][0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                now = time.time()
                self._local_counts[api_name] = [t for t in self._local_counts[api_name] if now - t < 1.0]
                
            self._local_counts[api_name].append(now)

rate_limiter = RateLimiter()

def rate_limit(api_name: str):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not settings.use_mock_data:
                await rate_limiter.wait_for_capacity(api_name)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
