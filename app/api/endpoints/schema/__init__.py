"""Schema designer, validation, generation, and jobs API endpoints module."""

from fastapi import APIRouter, status

from app.api.endpoints.schema import export, generation, jobs, validation
from app.api.endpoints.schema.designer import (
    delete_schema,
    get_schema_stats,
    import_schema,
    load_schema,
    put_schema,
    save_schema,
)
from app.schemas.schema_design import SchemaModel

router = APIRouter()

# Register core designer endpoints directly to the parent schema router
router.get("/stats")(get_schema_stats)
router.get("", response_model=SchemaModel)(load_schema)
router.post("", status_code=status.HTTP_200_OK)(save_schema)
router.put("", status_code=status.HTTP_200_OK)(put_schema)
router.delete("", status_code=status.HTTP_200_OK)(delete_schema)
router.post("/import", response_model=SchemaModel)(import_schema)

# Include refactored sub-routers
router.include_router(validation.router)
router.include_router(generation.router)
router.include_router(jobs.router)
router.include_router(export.router)
