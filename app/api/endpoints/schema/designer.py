from fastapi import Depends, HTTPException, status

from app.api.endpoints.schema.helpers import DEFAULT_SCHEMA
from app.platform.container import get_persistence_provider
from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.persistence.resolver import ProjectResolver
from app.schemas.schema_design import SchemaModel


async def load_schema(
    db: PersistenceProvider = Depends(get_persistence_provider),
) -> SchemaModel:
    """Loads the currently saved active schema state from SQLite."""
    project_id = ProjectResolver.get_active_project_id()
    try:
        schema_dict = await db.get_active_schema(project_id=project_id)
        if not schema_dict:
            # Verify and ensure default project exists
            if not await db.get_project(project_id):
                await db.create_project(project_id, "Default Project")

            schema_dict = await db.save_schema(
                project_id=project_id,
                version=1,
                tables=DEFAULT_SCHEMA["tables"],
                relationships=DEFAULT_SCHEMA.get("relationships", []),
            )

        return SchemaModel(
            tables=schema_dict["tables"],
            relationships=schema_dict.get("relationships", []),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load schema: {exc}",
        ) from exc


async def save_schema(
    schema: SchemaModel,
    db: PersistenceProvider = Depends(get_persistence_provider),
) -> dict[str, str]:
    """Saves the current schema state to SQLite."""
    project_id = ProjectResolver.get_active_project_id()
    try:
        # Determine next increment version num
        current_schema = await db.get_active_schema(project_id=project_id)
        next_version = 1
        if current_schema:
            next_version = current_schema["version"] + 1

        tables_dict = [t.model_dump(by_alias=True) for t in schema.tables]
        relationships_dict = [r.model_dump(by_alias=True) for r in schema.relationships]

        await db.save_schema(
            project_id=project_id,
            version=next_version,
            tables=tables_dict,
            relationships=relationships_dict,
        )
        return {"status": "success", "message": "Schema saved successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save schema: {exc}",
        ) from exc


async def put_schema(
    schema: SchemaModel,
    db: PersistenceProvider = Depends(get_persistence_provider),
) -> dict[str, str]:
    """Updates/Saves the current schema state to SQLite."""
    return await save_schema(schema, db)


async def delete_schema(
    db: PersistenceProvider = Depends(get_persistence_provider),
) -> dict[str, str]:
    """Deactivates/deletes the active schema state in SQLite."""
    project_id = ProjectResolver.get_active_project_id()
    try:
        await db.deactivate_schema(project_id=project_id)
        return {"status": "success", "message": "Schema deleted successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete schema: {exc}",
        ) from exc
