import contextlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func

from app.api.deps import get_runtime_provider
from app.api.endpoints.schema.generation import cancel_generation
from app.api.endpoints.schema.helpers import (
    RuntimeProviderType,
    _safe_decode,
)
from app.platform.container import get_persistence_provider
from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.platform.providers.sqlite_models import (
    DatasetMetadata,
    ExportHistory,
    Job,
    Project,
    Schema,
    ValidationHistory,
)
from app.schemas.schema_design import JobModel

router = APIRouter()


@router.get("/jobs", response_model=list[JobModel])
async def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    search: str | None = None,
    db: PersistenceProvider = Depends(get_persistence_provider),
    runtime: RuntimeProviderType = Depends(get_runtime_provider),
) -> list[JobModel]:
    """Lists all historical and active background jobs from SQLite, with optional filters.

    SQLite is the authoritative source of truth for all job records.
    The RuntimeProvider is consulted only to merge live progress details
    for jobs that are actively running.
    """
    sqlite_jobs = await db.list_jobs()

    jobs = []
    for job_data in sqlite_jobs:
        job_id = job_data.get("jobId") or job_data.get("id", "")
        j_type = job_data.get("type", "")
        j_status = job_data.get("status", "")

        # Apply filters
        if status and j_status.lower() != status.lower():
            continue
        if job_type and j_type.lower() != job_type.lower():
            continue
        if search:
            search_lower = search.lower()
            if (
                search_lower not in job_id.lower()
                and search_lower not in j_type.lower()
            ):
                continue

        # Merge live progress from RuntimeProvider cache if available
        merged_job_dict = dict(job_data)
        with contextlib.suppress(Exception):
            cache_bytes = await runtime.get(f"jobs:{job_id}")
            if cache_bytes:
                cached = json.loads(_safe_decode(cache_bytes))
                # Only take progress/details from cache — status truth stays SQLite
                for k in ("progress", "details", "resultSummary", "errorMessage"):
                    if k in cached:
                        merged_job_dict[k] = cached[k]

        with contextlib.suppress(Exception):
            jobs.append(JobModel(**merged_job_dict))

    return jobs


@router.get("/jobs/{job_id}", response_model=JobModel)
async def get_job_details(
    job_id: str,
    db: PersistenceProvider = Depends(get_persistence_provider),
    runtime: RuntimeProviderType = Depends(get_runtime_provider),
) -> JobModel:
    """Retrieves full details of a specific operation job from SQLite."""
    job_dict = await db.get_job(job_id)
    if not job_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job session {job_id} not found.",
        )

    # Merge live progress from RuntimeProvider cache if available
    merged_job_dict = dict(job_dict)
    with contextlib.suppress(Exception):
        cache_bytes = await runtime.get(f"jobs:{job_id}")
        if cache_bytes:
            cached = json.loads(_safe_decode(cache_bytes))
            for k in ("progress", "details", "resultSummary", "errorMessage"):
                if k in cached:
                    merged_job_dict[k] = cached[k]

    return JobModel(**merged_job_dict)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_from_history(
    job_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> dict[str, str]:
    """Cancels a running job directly from the history view."""
    return await cancel_generation(workflow_id=job_id, db=db, persistence=persistence)


@router.get("/stats")
async def get_dashboard_stats() -> dict[str, Any]:
    """Retrieve database count statistics for the dashboard dashboard panels."""
    try:
        with sqlite_db_manager.session() as s:
            total_projects = s.query(func.count(Project.id)).scalar() or 0
            total_schemas = s.query(func.count(Schema.id)).scalar() or 0
            total_jobs = s.query(func.count(Job.id)).scalar() or 0
            total_exports = s.query(func.count(ExportHistory.id)).scalar() or 0
            total_validations = s.query(func.count(ValidationHistory.id)).scalar() or 0
            total_rows = s.query(func.sum(DatasetMetadata.total_rows)).scalar() or 0

            # Validation stats breakdown
            passed_validations = (
                s.query(func.count(ValidationHistory.id))
                .filter(ValidationHistory.result_status == "passed")
                .scalar()
                or 0
            )
            failed_validations = (
                s.query(func.count(ValidationHistory.id))
                .filter(ValidationHistory.result_status == "failed")
                .scalar()
                or 0
            )

            return {
                "projects": total_projects,
                "schemas": total_schemas,
                "rows_generated": total_rows,
                "exports": total_exports,
                "jobs": total_jobs,
                "validations": total_validations,
                "passed_validations": passed_validations,
                "failed_validations": failed_validations,
            }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stats: {exc}",
        ) from exc
