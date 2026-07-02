import asyncio
import builtins
from collections.abc import Sequence
from typing import Any

from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.runtime.interfaces import RuntimeProvider


class MemoryPersistenceProvider(PersistenceProvider):
    """In-memory implementation of the PersistenceProvider interface for mock testing."""

    async def create_project(self, project_id: str, name: str) -> dict[str, Any]:
        raise NotImplementedError()

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
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
        from collections import defaultdict

        self._fnmatch = fnmatch
        self._defaultdict = defaultdict
        self._cache: dict[str, str] = {}
        self._sets: dict[str, builtins.set[str]] = self._defaultdict(builtins.set)
        self._queues: dict[str, asyncio.Queue[str]] = {}

    def _get_queue(self, queue_name: str) -> asyncio.Queue[str]:
        if queue_name not in self._queues:
            self._queues[queue_name] = asyncio.Queue()
        return self._queues[queue_name]

    async def get(self, key: str) -> str | None:
        return self._cache.get(key)

    async def set(self, key: str, value: str, _expire: int | None = None) -> None:
        self._cache[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._cache.pop(key, None)
            self._sets.pop(key, None)

    async def sadd(self, key: str, *members: str) -> None:
        for member in members:
            self._sets[key].add(member)

    async def srem(self, key: str, *members: str) -> None:
        if key in self._sets:
            for member in members:
                self._sets[key].discard(member)

    async def smembers(self, key: str) -> builtins.set[str]:
        return self._sets.get(key, builtins.set())

    async def keys(self, pattern: str) -> list[str]:
        return [k for k in self._cache if self._fnmatch.fnmatch(k, pattern)]

    async def push_to_queue(self, queue_name: str, payload: str) -> None:
        await self._get_queue(queue_name).put(payload)

    async def pop_from_queue(
        self, queue_name: str, timeout_seconds: int = 0
    ) -> str | None:
        q = self._get_queue(queue_name)
        if timeout_seconds > 0:
            try:
                return await asyncio.wait_for(q.get(), timeout=timeout_seconds)
            except TimeoutError:
                return None
        else:
            if q.empty():
                return None
            return q.get_nowait()

    async def ping(self) -> bool:
        return True
