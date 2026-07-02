import re
from typing import TYPE_CHECKING, Any

from app.platform.runtime.interfaces import RuntimeProvider

if TYPE_CHECKING:
    RuntimeProviderType = RuntimeProvider
else:
    RuntimeProviderType = RuntimeProvider

REDIS_KEY = "schema_designer:state"

RESERVED_KEYWORDS = {
    "select",
    "table",
    "order",
    "group",
    "user",
    "where",
    "join",
    "create",
    "delete",
    "update",
    "insert",
    "from",
    "into",
    "by",
    "index",
    "primary",
    "key",
    "foreign",
    "constraint",
    "null",
}
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _safe_decode(value: Any) -> str:
    """Safely decode bytes to string, or return string directly."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    return str(value)


DEFAULT_SCHEMA: dict[str, Any] = {
    "tables": [
        {
            "id": "1",
            "name": "users",
            "columns": [
                {
                    "id": "c1",
                    "name": "id",
                    "type": "INTEGER",
                    "isPrimaryKey": True,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "c2",
                    "name": "email",
                    "type": "VARCHAR",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "c3",
                    "name": "created_at",
                    "type": "TIMESTAMP",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "CURRENT_TIMESTAMP",
                },
            ],
        },
        {
            "id": "2",
            "name": "orders",
            "columns": [
                {
                    "id": "o1",
                    "name": "id",
                    "type": "INTEGER",
                    "isPrimaryKey": True,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "o2",
                    "name": "user_id",
                    "type": "INTEGER",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "o3",
                    "name": "total",
                    "type": "FLOAT",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "0.00",
                },
                {
                    "id": "o4",
                    "name": "status",
                    "type": "VARCHAR",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "'pending'",
                },
            ],
        },
    ],
    "relationships": [
        {
            "id": "r1",
            "name": "fk_orders_user_id",
            "sourceTableId": "2",
            "sourceColumnId": "o2",
            "targetTableId": "1",
            "targetColumnId": "c1",
            "type": "many-to-one",
            "isRequired": True,
            "cascadeDelete": True,
            "cascadeUpdate": True,
        }
    ],
}


async def update_job(
    runtime: "RuntimeProviderType",
    job_id: str,
    job_type: str = "generation",
    status: str = "Queued",
    progress: float = 0.0,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration: float = 0.0,
    result_summary: str | None = None,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
    *,
    persistence: Any = None,
) -> None:
    """Dual-write job state: SQLite (durable) + RuntimeProvider (progress cache).

    Args:
        runtime: The active RuntimeProvider for ephemeral progress caching.
        job_id: The unique job identifier.
        job_type: Type classification of the job (e.g. 'generation', 'export').
        status: Current job execution status string.
        progress: Completion percentage 0.0-100.0.
        started_at: ISO timestamp string when job started.
        finished_at: ISO timestamp string when job finished.
        duration: Elapsed execution duration in seconds.
        result_summary: Human-readable result summary.
        error_message: Error detail string if failed.
        details: Arbitrary metadata dictionary for progress tracking.
        persistence: Optional PersistenceProvider for SQLite writes.
    """
    import json
    from datetime import datetime

    from app.core.logging.logging import logger
    from app.telemetry.events import EventID

    # ── SQLite write (durable) ─────────────────────────────────
    if persistence is not None:
        try:
            existing = await persistence.get_job(job_id)
            if existing is None:
                # Ensure the project exists before creating the job (FK constraint)
                project = await persistence.get_project("default")
                if not project:
                    await persistence.create_project("default", "Default Project")
                await persistence.create_job(
                    job_id=job_id,
                    project_id="default",
                    job_type=job_type,
                    status=status,
                )
            await persistence.update_job_status(
                job_id=job_id,
                status=status,
                progress=round(progress, 2),
                duration=round(duration, 2),
                result_summary=result_summary,
                error_message=error_message,
                details=details,
            )
        except Exception as e:
            logger.error(
                EventID.LOG_ERROR,
                f"SQLite persistence write failed for job {job_id}",
                error=str(e),
                details={"job_id": job_id, "status": status},
            )
            # Publish Domain Event
            from app.platform.providers.sqlite import DomainEventDispatcher

            DomainEventDispatcher.dispatch(
                "persistence_failure", {"job_id": job_id, "error": str(e)}
            )
            raise

    # ── RuntimeProvider write (ephemeral progress cache) ────────────────────
    job_key = f"jobs:{job_id}"
    existing_bytes = await runtime.get(job_key)
    if existing_bytes:
        job_dict = json.loads(_safe_decode(existing_bytes))
    else:
        job_dict = {
            "jobId": job_id,
            "type": job_type,
            "status": status,
            "startedAt": started_at or datetime.utcnow().isoformat() + "Z",
            "finishedAt": None,
            "duration": 0.0,
            "progress": 0.0,
            "owner": None,
            "resultSummary": None,
            "errorMessage": None,
            "details": {},
        }
        await runtime.sadd("jobs:all_ids", job_id)

    job_dict["status"] = status
    job_dict["progress"] = round(progress, 2)
    job_dict["duration"] = round(duration, 2)

    if finished_at:
        job_dict["finishedAt"] = finished_at
    if result_summary is not None:
        job_dict["resultSummary"] = result_summary
    if error_message is not None:
        job_dict["errorMessage"] = error_message
    if details is not None:
        job_dict["details"] = details

    await runtime.set(job_key, json.dumps(job_dict))
