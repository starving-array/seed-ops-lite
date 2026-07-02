import json

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_redis
from app.api.endpoints.schema.generation import cancel_generation
from app.api.endpoints.schema.helpers import (
    RedisType,
    _safe_decode,
)
from app.schemas.schema_design import JobModel

router = APIRouter()


@router.get("/jobs", response_model=list[JobModel])
async def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    search: str | None = None,
    db: RedisType = Depends(get_redis),
) -> list[JobModel]:
    """Lists all historical and active background jobs, optionally applying filters."""
    job_ids_bytes = await db.smembers("jobs:all_ids")
    job_ids = [_safe_decode(j) for j in job_ids_bytes] if job_ids_bytes else []

    jobs = []
    for j_id in job_ids:
        job_bytes = await db.get(f"jobs:{j_id}")
        if job_bytes:
            job_dict = json.loads(_safe_decode(job_bytes))

            # Apply filters
            if status and job_dict.get("status", "").lower() != status.lower():
                continue
            if job_type and job_dict.get("type", "").lower() != job_type.lower():
                continue
            if search:
                search_lower = search.lower()
                id_match = search_lower in job_dict.get("jobId", "").lower()
                type_match = search_lower in job_dict.get("type", "").lower()
                if not (id_match or type_match):
                    continue

            jobs.append(JobModel(**job_dict))

    # Sort jobs by startedAt descending
    jobs.sort(key=lambda x: x.started_at, reverse=True)
    return jobs


@router.get("/jobs/{job_id}", response_model=JobModel)
async def get_job_details(
    job_id: str,
    db: RedisType = Depends(get_redis),
) -> JobModel:
    """Retrieves full details of a specific operation job."""
    job_bytes = await db.get(f"jobs:{job_id}")
    if not job_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job session {job_id} not found.",
        )

    job_dict = json.loads(_safe_decode(job_bytes))
    return JobModel(**job_dict)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_from_history(
    job_id: str,
    db: RedisType = Depends(get_redis),
) -> dict[str, str]:
    """Cancels a running job directly from the history view."""
    return await cancel_generation(workflow_id=job_id, db=db)
