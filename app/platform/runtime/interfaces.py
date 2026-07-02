import builtins
from abc import ABC, abstractmethod


class RuntimeProvider(ABC):
    """Abstract interface defining runtime caching, progress tracking, and queue management."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        """Fetch a value from transient cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        """Store a value in transient cache with optional expiry TTL."""
        pass

    @abstractmethod
    async def delete(self, *keys: str) -> None:
        """Remove keys from cache storage."""
        pass

    @abstractmethod
    async def sadd(self, key: str, *members: str) -> None:
        """Add members to a cached set group."""
        pass

    @abstractmethod
    async def srem(self, key: str, *members: str) -> None:
        """Remove members from a cached set group."""
        pass

    @abstractmethod
    async def smembers(self, key: str) -> builtins.set[str]:
        """Retrieve members belonging to a cached set."""
        pass

    @abstractmethod
    async def keys(self, pattern: str) -> list[str]:
        """Search cache keys matching a glob search pattern."""
        pass

    @abstractmethod
    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        """Push a message string onto a background worker execution task queue."""
        pass

    @abstractmethod
    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        """Fetch/pop a message from the queue blockingly or non-blockingly."""
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Verify provider connection liveness health."""
        pass
