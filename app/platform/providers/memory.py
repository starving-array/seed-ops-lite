import asyncio
import builtins
from collections.abc import Sequence
from typing import Any

from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.runtime.interfaces import RuntimeProvider


class MemoryPersistenceProvider(PersistenceProvider):
    """In-memory implementation of the PersistenceProvider interface for mock testing."""

    async def create_project(
        self,
        project_id: str,
        name: str,
        description: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError()

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        raise NotImplementedError()

    async def list_projects(self) -> list[dict[str, Any]]:
        raise NotImplementedError()

    async def save_schema(
        self, project_id: str, version: int, tables: list[Any], relationships: list[Any]
    ) -> dict[str, Any]:
        raise NotImplementedError()

    async def get_active_schema(self, project_id: str) -> dict[str, Any] | None:
        raise NotImplementedError()

    async def create_job(
        self, job_id: str, project_id: str, job_type: str, status: str
    ) -> dict[str, Any]:
        raise NotImplementedError()

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError()

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        progress: float,
        duration: float = 0.0,
        result_summary: str | None = None,
        error_message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError()

    async def list_jobs(
        self, project_id: str | None = None
    ) -> Sequence[dict[str, Any]]:
        raise NotImplementedError()

    async def log_validation_run(
        self, schema_id: str, status: str, issues: list[Any], duration_ms: float
    ) -> dict[str, Any]:
        raise NotImplementedError()

    async def set_app_setting(self, key: str, value: str) -> None:
        raise NotImplementedError()

    async def get_app_setting(self, key: str) -> str | None:
        raise NotImplementedError()

    async def log_caretaker_issue(
        self,
        issue_id: str,
        category: str,
        severity: str,
        source: str,
        affected_component: str,
        suggested_fix: str,
    ) -> dict[str, Any]:
        raise NotImplementedError()

    async def resolve_caretaker_issue(
        self, issue_id: str, resolution_notes: str
    ) -> None:
        raise NotImplementedError()


class MemoryRuntimeProvider(RuntimeProvider):
    """In-memory implementation of the RuntimeProvider interface for fallback / offline modes."""

    def __init__(self) -> None:
        import fnmatch
        import time
        from collections import defaultdict

        from app.platform.configuration.settings import platform_settings

        self._fnmatch = fnmatch
        self._defaultdict = defaultdict
        self._time = time
        self._platform_settings = platform_settings
        self._cache: dict[str, str] = {}
        self._expirations: dict[str, float] = {}
        self._sets: dict[str, builtins.set[str]] = self._defaultdict(builtins.set)
        self._queues: dict[str, asyncio.Queue[str]] = {}
        self._lru_keys: dict[str, float] = {}

        # Cache Metrics
        self.evicted_entries = 0
        self.expired_entries_removed = 0
        self.cleanup_runs = 0
        self.last_cleanup: str | None = None
        self._last_cleanup_time = self._time.time()

    def _touch(self, key: str) -> None:
        """Mark a key as recently used by updating its access timestamp."""
        self._lru_keys[key] = self._time.time()

    def _remove_expired_key(self, key: str) -> None:
        """Helper to remove an expired key across all storage blocks."""
        self._cache.pop(key, None)
        self._expirations.pop(key, None)
        self._sets.pop(key, None)
        self._queues.pop(key, None)
        self._lru_keys.pop(key, None)
        self.expired_entries_removed += 1

    def _lazy_cleanup_expired(self) -> None:
        """Remove expired keys dynamically and trigger periodic full cleanups."""
        now = self._time.time()
        expired_keys = [k for k, exp in self._expirations.items() if now > exp]
        for key in expired_keys:
            self._remove_expired_key(key)

        interval = self._platform_settings.RUNTIME_MEMORY_CLEANUP_INTERVAL_SECONDS
        if now - self._last_cleanup_time >= interval:
            self.run_periodic_cleanup()

    def run_periodic_cleanup(self) -> None:
        """Performs a full scan and eviction of all expired cache entries."""
        import datetime

        from app.core.logging.logging import logger
        from app.telemetry.events import EventID

        now = self._time.time()
        start_time = self._time.time()
        self.cleanup_runs += 1
        self.last_cleanup = (
            datetime.datetime.fromtimestamp(now, tz=datetime.UTC).isoformat() + "Z"
        )
        self._last_cleanup_time = now

        expired_keys = [k for k, exp in self._expirations.items() if now > exp]
        for key in expired_keys:
            self._remove_expired_key(key)

        duration = self._time.time() - start_time
        logger.info(
            EventID.LOG_INFO,
            f"TTL cleanup completed. Expired entries removed: {len(expired_keys)}.",
            details={
                "removed_count": len(expired_keys),
                "duration_seconds": duration,
            },
        )

    def _enforce_capacity(self) -> None:
        """Enforces maximum entries cache capacity limits via LRU eviction."""
        max_entries = self._platform_settings.RUNTIME_MEMORY_CACHE_MAX_ENTRIES
        if max_entries <= 0:
            return

        self._lazy_cleanup_expired()

        current_entries = len(self._lru_keys)
        if current_entries <= max_entries:
            return

        from app.core.logging.logging import logger
        from app.telemetry.events import EventID

        logger.info(EventID.LOG_INFO, "LRU eviction started.")

        # Sort keys by access time ascending
        sorted_keys = sorted(self._lru_keys.items(), key=lambda x: x[1])
        excess = current_entries - max_entries
        batch_size = max(
            self._platform_settings.RUNTIME_MEMORY_EVICTION_BATCH_SIZE, excess
        )

        to_evict = [k for k, _ in sorted_keys[:batch_size]]
        for key in to_evict:
            if key in self._lru_keys:
                self._lru_keys.pop(key, None)
                self._cache.pop(key, None)
                self._expirations.pop(key, None)
                self._sets.pop(key, None)
                self._queues.pop(key, None)
                self.evicted_entries += 1

        logger.info(
            EventID.LOG_INFO,
            f"Keys evicted: {len(to_evict)} entries removed.",
            details={"evicted_count": len(to_evict)},
        )

    def _get_queue(self, queue_name: str) -> asyncio.Queue[str]:
        if queue_name not in self._queues:
            self._queues[queue_name] = asyncio.Queue()
        return self._queues[queue_name]

    async def get(self, key: str) -> str | None:
        self._lazy_cleanup_expired()
        if key in self._expirations and self._time.time() > self._expirations[key]:
            self._remove_expired_key(key)
            return None
        if key in self._cache:
            self._touch(key)
        return self._cache.get(key)

    async def set(self, key: str, value: str, _expire: int | None = None) -> None:
        self._cache[key] = value
        self._touch(key)
        if _expire is not None:
            self._expirations[key] = self._time.time() + _expire
        else:
            self._expirations.pop(key, None)
        self._enforce_capacity()

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._cache.pop(key, None)
            self._expirations.pop(key, None)
            self._sets.pop(key, None)
            self._queues.pop(key, None)
            self._lru_keys.pop(key, None)

    async def sadd(self, key: str, *members: str) -> None:
        for member in members:
            self._sets[key].add(member)
        self._touch(key)
        self._enforce_capacity()

    async def srem(self, key: str, *members: str) -> None:
        if key in self._sets:
            for member in members:
                self._sets[key].discard(member)
            self._touch(key)

    async def smembers(self, key: str) -> builtins.set[str]:
        if key in self._sets:
            self._touch(key)
        return self._sets.get(key, builtins.set())

    async def keys(self, pattern: str) -> list[str]:
        self._lazy_cleanup_expired()
        now = self._time.time()
        active_keys = []
        for k in (
            list(self._cache.keys())
            + list(self._sets.keys())
            + list(self._queues.keys())
        ):
            if k in self._expirations and now > self._expirations[k]:
                self._remove_expired_key(k)
            else:
                active_keys.append(k)
        unique_active = sorted(set(active_keys))
        for k in unique_active:
            self._touch(k)
        return [k for k in unique_active if self._fnmatch.fnmatch(k, pattern)]

    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        await self._get_queue(queue_name).put(payload)
        self._touch(queue_name)
        self._enforce_capacity()

    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        q = self._get_queue(queue_name)
        self._touch(queue_name)
        if timeout_seconds > 0:
            try:
                res = await asyncio.wait_for(q.get(), timeout=timeout_seconds)
                self._touch(queue_name)
                return res
            except TimeoutError:
                return None
        else:
            if q.empty():
                return None
            res = q.get_nowait()
            self._touch(queue_name)
            return res

    async def ping(self) -> bool:
        return True
