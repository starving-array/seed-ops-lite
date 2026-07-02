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


class HealthResponse(BaseModel):
    """Pydantic model representing the health status response."""

    status: str = Field(
        description="Overall status of the application ('healthy' or 'unhealthy')"
    )
    version: str = Field(description="The application version")
    environment: str = Field(description="The deployment environment")
    uptime: float = Field(description="Application uptime in seconds")
    python_version: str = Field(description="The runtime Python version")
    redis_status: str = Field(description="Redis status ('healthy' or 'unhealthy')")
    startup_time: str = Field(description="ISO 8601 formatted startup timestamp")
    storage_mode: str = Field(
        description="Active storage backend ('redis' or 'memory')"
    )
    services: dict[str, ServiceStatus] = Field(
        description="Status breakdown of sub-services"
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check application health status",
)
async def health_check(response: Response) -> HealthResponse:
    """Retrieve application and system health check metrics.

    Checks the health of required backend dependencies such as Redis.

    Args:
        response: The response object used to dynamically set status code on failure.

    Returns:
        HealthResponse: The structured health status report.
    """
    from app.core.storage.client import is_local_memory_mode

    local_mem = is_local_memory_mode()
    storage_mode_str = "memory" if local_mem else "redis"

    redis_healthy = await redis_manager.check_health()
    redis_status_str = "healthy" if redis_healthy else "unhealthy"

    services = {
        "redis": ServiceStatus(
            status=redis_status_str,
            details=None if redis_healthy else "Connection failed or timed out",
        )
    }

    overall_healthy = True if local_mem else redis_healthy

    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if overall_healthy else "unhealthy",
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        uptime=round(get_uptime(), 2),
        python_version=get_python_version(),
        redis_status=redis_status_str,
        startup_time=get_startup_time_iso(),
        storage_mode=storage_mode_str,
        services=services,
    )
