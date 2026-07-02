import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.exceptions.exceptions import DatabaseConnectionError
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.runtime.manager import RuntimeManager


@pytest.mark.asyncio
async def test_runtime_manager_redis_available() -> None:
    """Test RuntimeManager behavior when Redis connection succeeds on startup."""
    rm = RuntimeManager()
    with (
        patch(
            "app.core.lifecycle.redis.redis_manager.connect",
            AsyncMock(),
        ),
        patch.object(rm.redis_provider, "ping", AsyncMock(return_value=True)),
    ):
        await rm.initialize()
        assert rm.mode == "redis"
        assert await rm.ping() is True
        await rm.close()


@pytest.mark.asyncio
async def test_runtime_manager_redis_unavailable_fallback() -> None:
    """Test RuntimeManager automatic fallback to memory when Redis connection fails."""
    rm = RuntimeManager()
    events = []

    def log_event(name: str, _payload: dict) -> None:
        events.append(name)

    DomainEventDispatcher.register(log_event)

    with patch.object(
        rm.redis_provider, "ping", AsyncMock(side_effect=Exception("Redis down"))
    ):
        await rm.initialize()
        assert rm.mode == "memory"
        assert "RuntimeFallbackActivated" in events
        assert rm.is_monitoring is True
        await rm.close()


@pytest.mark.asyncio
async def test_runtime_manager_dynamic_fallback() -> None:
    """Test that a mid-operation Redis connection loss triggers transparent fallback to memory."""
    rm = RuntimeManager()
    with (
        patch(
            "app.core.lifecycle.redis.redis_manager.connect",
            AsyncMock(),
        ),
        patch.object(rm.redis_provider, "ping", AsyncMock(return_value=True)),
    ):
        await rm.initialize()
        assert rm.mode == "redis"

    # Mock get operation to raise connection failure
    with patch.object(
        rm.redis_provider,
        "get",
        AsyncMock(side_effect=DatabaseConnectionError("Disconnected")),
    ):
        # Set values in memory cache beforehand
        await rm.memory_provider.set("test_key", "memory_value")

        # The call should fail on Redis, trigger fallback, and return memory_value
        val = await rm.get("test_key")
        assert val == "memory_value"
        assert rm.mode == "memory"
        assert rm.is_monitoring is True
        await rm.close()


@pytest.mark.asyncio
async def test_runtime_manager_recovery() -> None:
    """Test RuntimeManager background thread successfully polls and recovers to Redis mode."""
    rm = RuntimeManager()
    # Initialize in fallback memory mode
    with patch.object(
        rm.redis_provider, "ping", AsyncMock(side_effect=Exception("Down"))
    ):
        await rm.initialize()
        assert rm.mode == "memory"

    # Now make ping succeed and trigger recovery
    with (
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS",
            0.01,
        ),
        patch("app.core.lifecycle.redis.redis_manager.connect", AsyncMock()),
        patch.object(rm.redis_provider, "ping", AsyncMock(return_value=True)),
    ):

        # Give it a brief moment for the recovery task to wake up and process
        await asyncio.sleep(0.05)
        assert rm.mode == "redis"
        assert rm.reconnect_count == 1
        assert rm.last_reconnection_time is not None
        await rm.close()


@pytest.mark.asyncio
async def test_health_endpoint_runtime_status(client: AsyncClient) -> None:
    """Test the extended health check endpoint returns runtime_status details."""
    with patch(
        "app.core.lifecycle.redis.redis_manager.check_health",
        new_callable=AsyncMock,
        return_value=True,
    ):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "runtime_status" in data
        assert "provider" in data["runtime_status"]
        assert "redis_status" in data["runtime_status"]
        assert "connection_status" in data["runtime_status"]
        assert "reconnect_count" in data["runtime_status"]
        assert "mode" in data["runtime_status"]
