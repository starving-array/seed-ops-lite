import json

from fastapi import Depends, HTTPException, status

from app.api.deps import get_redis
from app.api.endpoints.schema.helpers import (
    DEFAULT_SCHEMA,
    REDIS_KEY,
    RedisType,
)
from app.schemas.schema_design import SchemaModel


async def load_schema(
    db: RedisType = Depends(get_redis),
) -> SchemaModel:
    """Loads the currently saved schema state from Redis."""
    try:
        raw_state = await db.get(REDIS_KEY)
        if not raw_state:
            return SchemaModel(**DEFAULT_SCHEMA)
        return SchemaModel(**json.loads(raw_state))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load schema: {exc}",
        ) from exc


async def save_schema(
    schema: SchemaModel,
    db: RedisType = Depends(get_redis),
) -> dict[str, str]:
    """Saves the current schema state to Redis."""
    try:
        serialized = json.dumps(schema.model_dump(by_alias=True))
        await db.set(REDIS_KEY, serialized)
        return {"status": "success", "message": "Schema saved successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save schema: {exc}",
        ) from exc
