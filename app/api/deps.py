"""Dependency injection providers for FastAPI endpoints."""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.lifecycle.redis import redis_manager


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:  # type: ignore[type-arg]
    """Dependency provider for retrieving a Redis client.

    Retrieves a client from the manager's connection pool.
    """
    client = redis_manager.get_client()
    try:
        yield client
    finally:
        await client.close()
