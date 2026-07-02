"""Schema designer, validation, generation, and jobs API endpoints module."""

from fastapi import APIRouter, status

from app.api.endpoints.schema import export, generation, jobs, validation
from app.api.endpoints.schema.designer import load_schema, save_schema
from app.schemas.schema_design import SchemaModel

router = APIRouter()

# Register core designer endpoints directly to the parent schema router
router.get("", response_model=SchemaModel)(load_schema)
router.post("", status_code=status.HTTP_200_OK)(save_schema)

# Include refactored sub-routers
router.include_router(validation.router)
router.include_router(generation.router)
router.include_router(jobs.router)
router.include_router(export.router)
