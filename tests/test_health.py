"""Integration tests for the health endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_healthy(client: AsyncClient) -> None:
    """Test the /health endpoint when all dependencies are healthy.

    Args:
        client: The HTTPX async test client.
    """
    from app.platform.runtime.manager import RuntimeManager

    mock_rm = MagicMock(spec=RuntimeManager)
    mock_rm.mode = "redis"
    mock_rm.reconnect_count = 0
    mock_rm.last_reconnection_time = None

    with (
        patch(
            "app.platform.container.get_runtime_provider",
            return_value=mock_rm,
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
    from app.platform.runtime.manager import RuntimeManager

    mock_rm = MagicMock(spec=RuntimeManager)
    mock_rm.mode = "memory"
    mock_rm.reconnect_count = 0
    mock_rm.last_reconnection_time = None

    with patch(
        "app.platform.container.get_runtime_provider",
        return_value=mock_rm,
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
    from app.platform.runtime.manager import RuntimeManager

    mock_rm = MagicMock(spec=RuntimeManager)
    mock_rm.mode = "redis"
    mock_rm.reconnect_count = 0
    mock_rm.last_reconnection_time = None

    with (
        patch(
            "app.platform.providers.sqlite_db.sqlite_db_manager.verify_health",
            side_effect=Exception("Database connection error"),
        ),
        patch(
            "app.platform.container.get_runtime_provider",
            return_value=mock_rm,
        ),
    ):
        response = await client.get("/health")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["services"]["sqlite"]["status"] == "unhealthy"
