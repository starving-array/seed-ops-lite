import builtins

from app.platform.runtime.interfaces import RuntimeProvider


class RedisRuntimeProvider(RuntimeProvider):
    """Redis-backed implementation of the RuntimeProvider interface."""

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

    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        raise NotImplementedError()

    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        raise NotImplementedError()

    async def ping(self) -> bool:
        raise NotImplementedError()
