import asyncio
import builtins
import contextlib
import datetime
from typing import Any

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.providers.memory import MemoryRuntimeProvider
from app.platform.providers.redis import RedisRuntimeProvider
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.runtime.interfaces import RuntimeProvider
from app.telemetry.events import EventID


class RuntimeManager(RuntimeProvider):
    """Orchestrates runtime caching, fallback switches, and automatic recovery protocols."""

    def __init__(self) -> None:
        self.redis_provider = RedisRuntimeProvider()
        self.memory_provider = MemoryRuntimeProvider()
        self.active_provider: RuntimeProvider = self.memory_provider
        self.mode = "memory"  # 'redis' | 'memory'
        self.reconnect_count = 0
        self.last_reconnection_time: str | None = None
        self.is_monitoring = False
        self._monitor_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        """Initialize connection checks and select initial active provider."""
        from app.core.lifecycle.redis import redis_manager

        try:
            # Best-effort connect: if Redis is unreachable, connect() raises but
            # we still attempt ping() through the provider to decide mode.
            with contextlib.suppress(Exception):
                if redis_manager._pool is None:
                    await redis_manager.connect()

            if await self.redis_provider.ping():
                self.active_provider = self.redis_provider
                self.mode = "redis"
                DomainEventDispatcher.dispatch("RuntimeStarted", {"provider": "redis"})
                DomainEventDispatcher.dispatch("RedisConnected", {})
                logger.info(
                    EventID.LOG_INFO,
                    "Runtime platform started in REDIS mode.",
                )
                return
        except Exception as e:
            logger.debug(
                EventID.LOG_INFO,
                "Initial Redis ping failed. Fallback mode will activate.",
                error=str(e),
            )

        self.active_provider = self.memory_provider
        self.mode = "memory"
        DomainEventDispatcher.dispatch("RuntimeStarted", {"provider": "memory"})
        DomainEventDispatcher.dispatch(
            "RuntimeFallbackActivated", {"reason": "Initial connection failed"}
        )
        logger.warning(
            EventID.LOG_WARNING,
            "Failed to connect to Redis. Runtime fallback activated using in-memory mode.",
        )
        self.start_recovery_monitor()

    async def close(self) -> None:
        """Clean shutdown and cancel background monitoring tasks."""
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task
        DomainEventDispatcher.dispatch("RuntimeStopped", {})
        logger.info(EventID.LOG_INFO, "Runtime platform stopped.")

    def start_recovery_monitor(self) -> None:
        """Start the background poll recovery loop if not already running."""
        if self.is_monitoring or not platform_settings.RUNTIME_MEMORY_FALLBACK_ENABLED:
            return
        self.is_monitoring = True
        self._monitor_task = asyncio.create_task(self._poll_redis_recovery())

    async def _poll_redis_recovery(self) -> None:
        """Periodically check Redis availability to restore primary state."""
        interval = platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS
        from app.core.lifecycle.redis import redis_manager

        while self.mode == "memory":
            await asyncio.sleep(interval)
            try:
                # Attempt to refresh pool connections
                with contextlib.suppress(Exception):
                    await redis_manager.connect()

                if await self.redis_provider.ping():
                    self.mode = "redis"
                    self.active_provider = self.redis_provider
                    self.reconnect_count += 1
                    self.last_reconnection_time = datetime.datetime.utcnow().isoformat()
                    DomainEventDispatcher.dispatch("RedisConnected", {})
                    DomainEventDispatcher.dispatch(
                        "RuntimeRecovered",
                        {
                            "reconnect_count": self.reconnect_count,
                            "time": self.last_reconnection_time,
                        },
                    )
                    DomainEventDispatcher.dispatch(
                        "RuntimeProviderChanged", {"new_provider": "redis"}
                    )
                    logger.info(
                        EventID.LOG_INFO,
                        "Redis connection recovered. Switched runtime provider to REDIS.",
                        details={
                            "reconnect_count": self.reconnect_count,
                            "time": self.last_reconnection_time,
                        },
                    )
                    break
            except Exception as e:
                logger.debug(
                    EventID.LOG_INFO,
                    "Redis recovery poll failed, retrying.",
                    error=str(e),
                )
        self.is_monitoring = False

    async def _execute(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a runtime method, falling back to memory if the active Redis call fails."""
        if self.mode == "redis":
            try:
                method = getattr(self.redis_provider, method_name)
                return await method(*args, **kwargs)
            except Exception as e:
                logger.error(
                    EventID.LOG_ERROR,
                    f"Runtime redis method {method_name} failed. Falling back to Memory.",
                    error=str(e),
                )
                self.mode = "memory"
                self.active_provider = self.memory_provider
                from app.core.lifecycle.redis import redis_manager

                with contextlib.suppress(Exception):
                    await redis_manager.disconnect()
                DomainEventDispatcher.dispatch("RedisDisconnected", {})
                DomainEventDispatcher.dispatch(
                    "RuntimeFallbackActivated", {"reason": str(e)}
                )
                DomainEventDispatcher.dispatch(
                    "RuntimeProviderChanged", {"new_provider": "memory"}
                )
                self.start_recovery_monitor()

        method = getattr(self.memory_provider, method_name)
        return await method(*args, **kwargs)

    async def get(self, key: str) -> str | None:
        return await self._execute("get", key)  # type: ignore[no-any-return]

    async def set(self, key: str, value: str, expire: int | None = None) -> None:
        await self._execute("set", key, value, expire)

    async def delete(self, *keys: str) -> None:
        await self._execute("delete", *keys)

    async def sadd(self, key: str, *members: str) -> None:
        await self._execute("sadd", key, *members)

    async def srem(self, key: str, *members: str) -> None:
        await self._execute("srem", key, *members)

    async def smembers(self, key: str) -> builtins.set[str]:
        return await self._execute("smembers", key)  # type: ignore[no-any-return]

    async def keys(self, pattern: str) -> list[str]:
        return await self._execute("keys", pattern)  # type: ignore[no-any-return]

    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        await self._execute("push_to_queue", queue_name, payload)

    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        return await self._execute("pop_from_queue", queue_name, timeout_seconds)  # type: ignore[no-any-return]

    async def ping(self) -> bool:
        if self.mode == "redis":
            try:
                return await self.redis_provider.ping()
            except Exception:
                return False
        return True
