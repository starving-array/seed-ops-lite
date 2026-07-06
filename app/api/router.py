"""Main router routing HTTP endpoints to controllers."""

from fastapi import APIRouter

from app.api.endpoints import health, projects, schema, workflow

api_router = APIRouter()
api_router.include_router(health.router, tags=["System"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(schema.router, prefix="/schema", tags=["Schema"])
api_router.include_router(workflow.router, prefix="/workflows", tags=["Workflow"])
