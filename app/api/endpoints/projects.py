import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.platform.container import get_persistence_provider
from app.platform.persistence.interfaces import PersistenceProvider

router = APIRouter()


class ProjectCreate(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str | None = "pending"


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    tables: int
    version: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: PersistenceProvider = Depends(get_persistence_provider),
) -> list[ProjectResponse]:
    """Retrieve list of all projects workspace metadata from database."""
    try:
        projects = await db.list_projects()
        return [ProjectResponse(**p) for p in projects]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list projects: {exc}",
        ) from exc


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project: ProjectCreate,
    db: PersistenceProvider = Depends(get_persistence_provider),
) -> ProjectResponse:
    """Create a new project workspace record in database."""
    try:
        existing = await db.get_project(project.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Project with ID '{project.id}' already exists.",
            )
        res = await db.create_project(
            project_id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
        )
        return ProjectResponse(**res)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {exc}",
        ) from exc
