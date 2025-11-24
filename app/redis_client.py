import asyncio
from typing import AsyncGenerator
import redis.asyncio as redis

from .config import get_settings

settings = get_settings()
_redis_instance: redis.Redis | None = None
_lock = asyncio.Lock()


async def get_redis() -> redis.Redis:
    global _redis_instance
    if _redis_instance is None:
        async with _lock:
            if _redis_instance is None:
                _redis_instance = redis.from_url(settings.redis_url)
    return _redis_instance


async def redis_dependency() -> AsyncGenerator[redis.Redis, None]:
    client = await get_redis()
    yield client


