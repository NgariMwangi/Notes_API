import json
from typing import Any, Optional
import redis.asyncio as redis

from .config import get_settings
from .schemas import Note

settings = get_settings()


def _note_cache_key(note_id: int) -> str:
    return f"note:{note_id}"


async def get_cached_note(client: redis.Redis, note_id: int) -> Optional[Note]:
    data = await client.get(_note_cache_key(note_id))
    if not data:
        return None
    payload: dict[str, Any] = json.loads(data)
    return Note(**payload)


async def cache_note(client: redis.Redis, note: Note) -> None:
    await client.set(
        _note_cache_key(note.id),
        note.model_dump_json(),
        ex=settings.note_cache_ttl_seconds,
    )


async def invalidate_note_cache(client: redis.Redis, note_id: int) -> None:
    await client.delete(_note_cache_key(note_id))


