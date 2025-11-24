from typing import List
import redis.asyncio as redis

from .config import get_settings

settings = get_settings()


def _recent_key(ip: str) -> str:
    return f"recent:ip:{ip}"


async def push_recent_note(client: redis.Redis, ip: str, note_id: int) -> None:
    key = _recent_key(ip)
    async with client.pipeline() as pipe:
        pipe.lrem(key, 0, note_id)
        pipe.lpush(key, note_id)
        pipe.ltrim(key, 0, settings.recent_notes_limit - 1)
        pipe.expire(key, settings.rate_limit_window_seconds)
        await pipe.execute()


async def get_recent_notes(client: redis.Redis, ip: str) -> List[int]:
    key = _recent_key(ip)
    values = await client.lrange(key, 0, settings.recent_notes_limit - 1)
    return [int(v) for v in values]


