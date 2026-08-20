import logging
from typing import Any

import redis.asyncio as aioredis
from apps.api.src.core.config import settings

logger = logging.getLogger(__name__)

redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Get or create singleton async Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def check_redis_health() -> dict[str, Any]:
    """Check Redis connectivity."""
    try:
        client = get_redis_client()
        pong = await client.ping()
        return {
            "status": "healthy" if pong else "unhealthy",
            "connected": bool(pong),
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "status": "unhealthy",
            "connected": False,
            "error": str(e),
        }


async def close_redis() -> None:
    """Gracefully close Redis connection on shutdown."""
    global redis_client
    if redis_client is not None:
        await redis_client.close()
        redis_client = None
