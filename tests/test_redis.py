"""Unit tests for the Redis connection manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.exceptions import DatabaseConnectionError
from app.core.lifecycle.redis import RedisManager


@pytest.mark.asyncio
async def test_redis_connect_success() -> None:
    """Test successful Redis connection and pool initialization."""
    manager = RedisManager()

    mock_pool = AsyncMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.ping.return_value = True

    with (
        patch("redis.asyncio.ConnectionPool", return_value=mock_pool),
        patch.object(manager, "get_client", return_value=mock_client),
    ):
        await manager.connect()
        assert manager._pool is mock_pool
        mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_redis_connect_failure() -> None:
    """Test Redis connection failure raising DatabaseConnectionError."""
    manager = RedisManager()

    mock_pool = AsyncMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.ping.side_effect = RedisConnectionError("Connection refused")

    with (
        patch("redis.asyncio.ConnectionPool", return_value=mock_pool),
        patch.object(manager, "get_client", return_value=mock_client),
    ):
        with pytest.raises(DatabaseConnectionError) as exc_info:
            await manager.connect()

        assert "Could not connect to Redis" in str(exc_info.value)
        assert manager._pool is None


@pytest.mark.asyncio
async def test_redis_get_client_uninitialized() -> None:
    """Test that get_client raises DatabaseConnectionError when uninitialized."""
    manager = RedisManager()
    with pytest.raises(DatabaseConnectionError) as exc_info:
        manager.get_client()
    assert "Redis connection pool is not initialized" in str(exc_info.value)


@pytest.mark.asyncio
async def test_redis_check_health_healthy() -> None:
    """Test check_health returns True when Redis is healthy."""
    manager = RedisManager()
    manager._pool = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.ping.return_value = True

    with patch.object(manager, "get_client", return_value=mock_client):
        result = await manager.check_health()
        assert result is True
        mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_redis_check_health_unhealthy() -> None:
    """Test check_health returns False when Redis ping raises exception."""
    manager = RedisManager()
    manager._pool = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.ping.side_effect = RedisConnectionError("Timeout")

    with patch.object(manager, "get_client", return_value=mock_client):
        result = await manager.check_health()
        assert result is False


@pytest.mark.asyncio
async def test_redis_disconnect() -> None:
    """Test successful teardown of the connection pool."""
    manager = RedisManager()
    mock_pool = AsyncMock()
    manager._pool = mock_pool

    await manager.disconnect()
    mock_pool.disconnect.assert_called_once()
    assert manager._pool is None
