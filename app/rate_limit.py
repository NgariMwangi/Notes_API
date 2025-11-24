from fastapi import HTTPException, status, Request, Depends
import redis.asyncio as redis

from .config import get_settings
from .redis_client import redis_dependency

settings = get_settings()


def _rate_limit_key(ip: str) -> str:
    return f"rate:ip:{ip}"


async def rate_limiter(
    request: Request,
    client: redis.Redis = Depends(redis_dependency),
) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = _rate_limit_key(client_ip)

    async with client.pipeline() as pipe:
        try:
            pipe.incr(key, 1)
            pipe.expire(key, settings.rate_limit_window_seconds, nx=True)
            current_count, _ = await pipe.execute()
        except redis.RedisError:
            # if Redis fails, skip throttling to favor availability.
            return

    if current_count and int(current_count) > settings.rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again later.",
        )


