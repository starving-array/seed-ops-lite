from __future__ import annotations

import builtins
import fnmatch
from typing import Any, cast


class BaseStorage:
    """Abstract interface defining required database/caching storage operations."""

    async def get(self, key: str) -> str | None:
        raise NotImplementedError()

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        raise NotImplementedError()

    async def delete(self, *keys: str) -> None:
        raise NotImplementedError()

    async def sadd(self, key: str, *members: str) -> None:
        raise NotImplementedError()

    async def srem(self, key: str, *members: str) -> None:
        raise NotImplementedError()

    async def smembers(self, key: str) -> builtins.set[str]:
        raise NotImplementedError()

    async def keys(self, pattern: str) -> list[str]:
        raise NotImplementedError()

    async def ping(self) -> bool:
        raise NotImplementedError()


class RedisStorage(BaseStorage):
    """Storage implementation backed by an active Redis client connection pool."""

    def __init__(self, client: Any) -> None:
        self.client = client

    async def get(self, key: str) -> str | None:
        val = await self.client.get(key)
        return cast(str | None, val)

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        if expire is not None:
            await self.client.setex(key, expire, value)
        else:
            await self.client.set(key, value)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self.client.delete(*keys)

    async def sadd(self, key: str, *members: str) -> None:
        if members:
            await self.client.sadd(key, *members)

    async def srem(self, key: str, *members: str) -> None:
        if members:
            await self.client.srem(key, *members)

    async def smembers(self, key: str) -> builtins.set[str]:
        res = await self.client.smembers(key)
        return set(res) if res else set()

    async def keys(self, pattern: str) -> list[str]:
        res = await self.client.keys(pattern)
        return [str(k) for k in res] if res else []

    async def ping(self) -> bool:
        try:
            return await self.client.ping() is True
        except Exception:
            return False


class MemoryStorage(BaseStorage):
    """Fallback in-memory storage implementation for local developer mode without Redis."""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._sets: dict[str, builtins.set[str]] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, _expire: int | None = None) -> None:
        self._data[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._data.pop(key, None)
            self._sets.pop(key, None)

    async def sadd(self, key: str, *members: str) -> None:
        if key not in self._sets:
            self._sets[key] = set()
        self._sets[key].update(members)

    async def srem(self, key: str, *members: str) -> None:
        if key in self._sets:
            self._sets[key].difference_update(members)

    async def smembers(self, key: str) -> builtins.set[str]:
        return set(self._sets.get(key, set()))

    async def keys(self, pattern: str) -> list[str]:
        # Filter all active keys in database matching glob pattern
        all_keys = list(self._data.keys()) + list(self._sets.keys())
        matched = fnmatch.filter(all_keys, pattern)
        return list(set(matched))

    async def ping(self) -> bool:
        return True
