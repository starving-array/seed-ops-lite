import builtins
import contextlib
from typing import Any

from app.core.lifecycle.redis import redis_manager
from app.core.storage.base import BaseStorage

_storage: BaseStorage | None = None
_is_local_memory_mode = False


class RuntimeDelegatingStorage(BaseStorage):
    """Dynamic storage engine that delegates calls to the active RuntimeProvider."""

    def _get_provider(self) -> Any:
        from app.platform.container import get_runtime_provider
        return get_runtime_provider()

    async def get(self, key: str) -> str | None:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                return await client.get(key)
        res_get = await provider.get(key)
        from typing import cast
        return cast(str | None, res_get)

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                if expire is not None:
                    await client.setex(key, expire, value)
                else:
                    await client.set(key, value)
                return
        await provider.set(key, value, expire)

    async def delete(self, *keys: str) -> None:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                if keys:
                    await client.delete(*keys)
                return
        await provider.delete(*keys)

    async def sadd(self, key: str, *members: str) -> None:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                if members:
                    await client.sadd(key, *members)
                return
        await provider.sadd(key, *members)

    async def srem(self, key: str, *members: str) -> None:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                if members:
                    await client.srem(key, *members)
                return
        await provider.srem(key, *members)

    async def smembers(self, key: str) -> builtins.set[str]:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                res = await client.smembers(key)
                import builtins as py_builtins
                return py_builtins.set(res)
        res_mem = await provider.smembers(key)
        from typing import cast
        return cast(builtins.set[str], res_mem)

    async def keys(self, pattern: str) -> list[str]:
        provider = self._get_provider()
        if hasattr(provider, "mode") and provider.mode == "redis":
            with contextlib.suppress(Exception):
                client = redis_manager.get_client()
                res = await client.keys(pattern)
                return list(res)
        res_keys = await provider.keys(pattern)
        from typing import cast
        return cast(list[str], res_keys)

    async def ping(self) -> bool:
        res_ping = await self._get_provider().ping()
        from typing import cast
        return cast(bool, res_ping)


_delegating_storage = RuntimeDelegatingStorage()


async def init_storage() -> None:
    """Initialize active storage client. (No-op as state dynamically delegates)"""
    pass


def get_storage() -> BaseStorage:
    """Get the active storage implementation instance.

    Returns:
        BaseStorage: The current storage manager instance.
    """
    return _delegating_storage


def is_local_memory_mode() -> bool:
    """Check if the application is running in local in-memory storage mode.

    Returns:
        bool: True if MemoryStorage is active, False otherwise.
    """
    from app.platform.container import get_runtime_provider
    provider = get_runtime_provider()
    if hasattr(provider, "mode"):
        res_mode = getattr(provider, "mode") == "memory"
        from typing import cast
        return cast(bool, res_mode)
    return True
