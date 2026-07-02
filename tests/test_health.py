"""Integration tests for the health endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient) -> None:
    """Test the /health endpoint when all dependencies are healthy.

    Args:
        client: The HTTPX async test client.
    """
    with (
        patch(
            "app.core.lifecycle.redis.redis_manager.check_health",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.core.storage.client.is_local_memory_mode",
            return_value=False,
        ),
    ):
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert data["services"]["redis"]["status"] == "healthy"
        assert data["services"]["redis"]["details"] is None


@pytest.mark.asyncio
async def test_health_endpoint_degraded(client: AsyncClient) -> None:
    """Test the /health endpoint when Redis is unhealthy but SQLite is healthy.

    Args:
        client: The HTTPX async test client.
    """
    with patch(
        "app.core.lifecycle.redis.redis_manager.check_health",
        new_callable=AsyncMock,
        return_value=False,
    ):
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["redis"]["status"] == "unhealthy"
        assert "failed" in data["services"]["redis"]["details"].lower()


@pytest.mark.asyncio
async def test_health_endpoint_unhealthy_sqlite(client: AsyncClient) -> None:
    """Test the /health endpoint when SQLite is unhealthy.

    Args:
        client: The HTTPX async test client.
    """
    with (
        patch(
            "app.platform.providers.sqlite_db.sqlite_db_manager.verify_health",
            side_effect=Exception("Database connection error"),
        ),
        patch(
            "app.core.lifecycle.redis.redis_manager.check_health",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        response = await client.get("/health")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["services"]["sqlite"]["status"] == "unhealthy"
