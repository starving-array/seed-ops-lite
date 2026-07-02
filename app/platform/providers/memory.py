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
