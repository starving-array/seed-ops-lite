"""Health check API endpoints."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from app.core.lifecycle.redis import redis_manager
from app.core.lifecycle.state import (
    get_python_version,
    get_startup_time_iso,
    get_uptime,
)
from app.core.settings.config import settings

router = APIRouter()


class ServiceStatus(BaseModel):
    """Pydantic model representing the status of a sub-service."""

    status: str = Field(
        description="Status of the sub-service ('healthy' or 'unhealthy')"
    )
    details: str | None = Field(
        default=None, description="Optional details or error message"
    )


class SQLiteStatus(BaseModel):
    """Detailed health status metrics of the SQLite database engine."""

    status: str = Field(description="SQLite status ('healthy' or 'unhealthy')")
    migration_version: str = Field(description="Active database migration version")
    database_path: str = Field(description="Database file path")
    connection_status: str = Field(
        description="Connection state ('connected' or 'disconnected')"
    )
    initialized: bool = Field(description="Is SQLite database initialized")
    migration_status: str = Field(
        description="Migration status ('completed' or 'pending')"
    )
    pending_migrations: list[str] = Field(description="Pending Alembic migrations list")
    last_successful_migration_at: str | None = Field(
        default=None, description="ISO timestamp of last migration success"
    )


class RuntimeStatus(BaseModel):
    """Detailed health status metrics of the Runtime Platform."""

    provider: str = Field(description="Name of the active runtime provider")
    redis_status: str = Field(
        description="Redis liveness status ('healthy' or 'unhealthy')"
    )
    connection_status: str = Field(
        description="Connection state ('connected' or 'disconnected')"
    )
    reconnect_count: int = Field(description="Total count of Redis reconnections")
    mode: str = Field(description="Current active runtime mode ('redis' or 'memory')")
    last_reconnection_time: str | None = Field(
        default=None, description="ISO timestamp of last reconnection"
    )


class HealthResponse(BaseModel):
    """Pydantic model representing the health status response."""

    status: str = Field(
        description="Overall status of the application ('healthy', 'degraded', or 'unhealthy')"
    )
    version: str = Field(description="The application version")
    environment: str = Field(description="The deployment environment")
    uptime: float = Field(description="Application uptime in seconds")
    python_version: str = Field(description="The runtime Python version")
    redis_status: str = Field(description="Redis status ('healthy' or 'unhealthy')")
    startup_time: str = Field(description="ISO 8601 formatted startup timestamp")
    storage_mode: str = Field(
        description="The system storage mode ('redis' or 'memory')"
    )
    sqlite_status: SQLiteStatus = Field(description="Detailed health metrics of SQLite")
    runtime_status: RuntimeStatus = Field(
        description="Detailed health metrics of the Runtime Platform"
    )
    services: dict[str, ServiceStatus] = Field(
        description="Dictionary containing services status breakdown"
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def health_check(response: Response) -> HealthResponse:
    """Retrieve application and system health check metrics.

    Checks the health of required backend dependencies such as Redis and SQLite.

    Args:
        response: The response object used to dynamically set status code on failure.

    Returns:
        HealthResponse: The structured health status report.
    """
    from app.core.storage.client import is_local_memory_mode
    from app.platform.providers.sqlite_db import sqlite_db_manager

    local_mem = is_local_memory_mode()
    storage_mode_str = "memory" if local_mem else "redis"

    redis_healthy = await redis_manager.check_health()
    redis_status_str = "healthy" if redis_healthy else "unhealthy"

    sqlite_healthy = True
    sqlite_details = None
    migration_version = "none"
    connection_status = "connected"

    initialized = False
    migration_status = "uninitialized"
    pending_migrations: list[str] = []
    last_successful_migration_at = None

    try:
        if not sqlite_db_manager._engine:
            sqlite_db_manager.initialize()
        sqlite_db_manager.verify_health()

        info = sqlite_db_manager.get_migration_info()
        initialized = info["initialized"]
        migration_status = info["migration_status"]
        pending_migrations = info["pending_migrations"]
        last_successful_migration_at = info["last_successful_migration_at"]
        migration_version = info["current_schema_version"]
    except Exception as e:
        sqlite_healthy = False
        sqlite_details = str(e)
        connection_status = "disconnected"

    from app.platform.container import get_runtime_provider
    from app.platform.runtime.manager import RuntimeManager

    try:
        runtime_prov = get_runtime_provider()
    except Exception:
        runtime_prov = None
    rm_provider_name = "unknown"
    rm_redis_status = "unhealthy"
    rm_connection_status = "disconnected"
    rm_reconnect_count = 0
    rm_mode = "memory"
    rm_last_reconnect_time = None

    if isinstance(runtime_prov, RuntimeManager):
        rm_provider_name = (
            "RedisRuntimeProvider"
            if runtime_prov.mode == "redis"
            else "MemoryRuntimeProvider"
        )
        rm_redis_status = "healthy" if runtime_prov.mode == "redis" else "unhealthy"
        rm_connection_status = (
            "connected" if runtime_prov.mode == "redis" else "disconnected"
        )
        rm_reconnect_count = runtime_prov.reconnect_count
        rm_mode = runtime_prov.mode
        rm_last_reconnect_time = runtime_prov.last_reconnection_time

    services = {
        "redis": ServiceStatus(
            status=redis_status_str,
            details=None if redis_healthy else "Connection failed or timed out",
        ),
        "sqlite": ServiceStatus(
            status="healthy" if sqlite_healthy else "unhealthy",
            details=sqlite_details,
        ),
    }

    if not sqlite_healthy:
        overall_status = "unhealthy"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif not redis_healthy or local_mem:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return HealthResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        uptime=round(get_uptime(), 2),
        python_version=get_python_version(),
        redis_status=redis_status_str,
        startup_time=get_startup_time_iso(),
        storage_mode=storage_mode_str,
        sqlite_status=SQLiteStatus(
            status="healthy" if sqlite_healthy else "unhealthy",
            migration_version=migration_version,
            database_path=sqlite_db_manager.db_path,
            connection_status=connection_status,
            initialized=initialized,
            migration_status=migration_status,
            pending_migrations=pending_migrations,
            last_successful_migration_at=last_successful_migration_at,
        ),
        runtime_status=RuntimeStatus(
            provider=rm_provider_name,
            redis_status=rm_redis_status,
            connection_status=rm_connection_status,
            reconnect_count=rm_reconnect_count,
            mode=rm_mode,
            last_reconnection_time=rm_last_reconnect_time,
        ),
        services=services,
    )
