import builtins

from app.core.exceptions.exceptions import DatabaseConnectionError
from app.core.lifecycle.redis import redis_manager
from app.platform.runtime.interfaces import RuntimeProvider


class RedisRuntimeProvider(RuntimeProvider):
    """Redis-backed implementation of the RuntimeProvider interface."""

    async def get(self, key: str) -> str | None:
        try:
            async with redis_manager.get_client() as client:
                return await client.get(key)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis get failed: {e}") from e

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        try:
            async with redis_manager.get_client() as client:
                await client.set(key, value, ex=expire)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis set failed: {e}") from e

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            async with redis_manager.get_client() as client:
                await client.delete(*keys)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis delete failed: {e}") from e

    async def sadd(self, key: str, *members: str) -> None:
        if not members:
            return
        try:
            async with redis_manager.get_client() as client:
                await client.sadd(key, *members)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis sadd failed: {e}") from e

    async def srem(self, key: str, *members: str) -> None:
        if not members:
            return
        try:
            async with redis_manager.get_client() as client:
                await client.srem(key, *members)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis srem failed: {e}") from e

    async def smembers(self, key: str) -> builtins.set[str]:
        try:
            async with redis_manager.get_client() as client:
                res = await client.smembers(key)
                return builtins.set(res)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis smembers failed: {e}") from e

    async def keys(self, pattern: str) -> list[str]:
        try:
            async with redis_manager.get_client() as client:
                res = await client.keys(pattern)
                return list(res)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis keys failed: {e}") from e

    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        try:
            async with redis_manager.get_client() as client:
                await client.rpush(queue_name, payload)
        except Exception as e:
            raise DatabaseConnectionError(f"Redis rpush failed: {e}") from e

    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        try:
            async with redis_manager.get_client() as client:
                if timeout_seconds > 0:
                    res = await client.blpop(queue_name, timeout=timeout_seconds)
                    if res:
                        return res[1]  # type: ignore[no-any-return]
                    return None
                return await client.lpop(queue_name)  # type: ignore[no-any-return]
        except Exception as e:
            raise DatabaseConnectionError(f"Redis pop failed: {e}") from e

    async def ping(self) -> bool:
        try:
            async with redis_manager.get_client() as client:
                return await client.ping() is True
        except Exception:
            return False
