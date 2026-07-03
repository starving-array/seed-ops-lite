import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.container import container
from app.platform.persistence.interfaces import PersistenceProvider
from app.platform.runtime.manager import RuntimeManager


@pytest.mark.asyncio
async def test_lazy_cache_replay_filtering() -> None:
    """Test cold cache read miss fallback & ephemeral replay key discard logic."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    rm.redis_provider.delete = AsyncMock(return_value=None)
    rm.redis_provider.set = AsyncMock(return_value=None)

    # 1. Initialize healthy
    await rm.initialize()
    rm.mode = "redis"
    rm.breaker_state = "CLOSED"

    # 2. Pause worker processing by switching to memory mode internally (to queue items)
    rm.mode = "memory"

    # 3. Fire writes to replay-allowed and replay-discard keys
    await rm.set("schema:metadata_key", "schema_val")  # Should replay
    await rm.set("progress:ephemeral_key", "progress_val")  # Should be skipped

    assert rm.unique_events == 2
    assert "schema:metadata_key" in rm._pending_keys
    assert "progress:ephemeral_key" in rm._pending_keys

    # 4. Recover and let worker process
    rm.mode = "redis"
    # Wait for background queue worker to drain
    await asyncio.sleep(0.1)

    # Verify metadata_key was processed, progress_key was discarded/skipped
    assert "schema:metadata_key" not in rm._pending_keys
    assert "progress:ephemeral_key" not in rm._pending_keys
    assert rm.skipped_events == 1  # progress_key was skipped

    await rm.close()


@pytest.mark.asyncio
async def test_lazy_cache_sqlite_fallback_and_populate() -> None:
    """Test read miss on Redis -> SQLite lookup -> Return -> Async Redis populate."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    # Redis has nothing (cold cache)
    rm.redis_provider.get = AsyncMock(return_value=None)
    rm.redis_provider.set = AsyncMock(return_value=None)

    await rm.initialize()
    rm.mode = "redis"
    rm.breaker_state = "CLOSED"

    # Mock SQLite persistence provider
    mock_pers = MagicMock()
    mock_pers.get_app_setting = AsyncMock(return_value="db_value")

    # Register mock persistence provider in DI container
    container.register(PersistenceProvider, lambda: mock_pers)

    try:
        # Read a lookup key (should miss on Redis, call SQLite, return, and async populate Redis)
        val = await rm.get("lookup:my_config")

        # Verify it returns SQLite value
        assert val == "db_value"
        mock_pers.get_app_setting.assert_called_once_with("my_config")

        # Wait for background task to execute set on Redis
        await asyncio.sleep(0.1)

        # Verify redis_provider.set was called to populate the cache asynchronously
        rm.redis_provider.set.assert_called_once()
        args, kwargs = rm.redis_provider.set.call_args
        assert args[0] == "lookup:my_config"
        assert args[1] == "db_value"
    finally:
        await rm.close()


@pytest.mark.asyncio
async def test_lazy_cache_repeated_reads() -> None:
    """Test that repeated reads hit cache (Redis/Memory) directly without querying SQLite again."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)

    # Setup initial mock behavior: first read misses, second read hits Redis
    redis_data = {}

    async def mock_get(key: str) -> str | None:
        return redis_data.get(key)

    async def mock_set(key: str, val: str, expire: int | None = None) -> None:
        _ = expire
        redis_data[key] = val

    rm.redis_provider.get = AsyncMock(side_effect=mock_get)
    rm.redis_provider.set = AsyncMock(side_effect=mock_set)

    await rm.initialize()
    rm.mode = "redis"
    rm.breaker_state = "CLOSED"

    # Mock SQLite persistence provider
    mock_pers = MagicMock()
    mock_pers.get_app_setting = AsyncMock(return_value="repeated_db_value")
    container.register(PersistenceProvider, lambda: mock_pers)

    try:
        # First read: Misses Redis, retrieves from SQLite, populates cache
        val1 = await rm.get("lookup:repeat_key")
        assert val1 == "repeated_db_value"
        mock_pers.get_app_setting.assert_called_once_with("repeat_key")

        # Wait for async Redis set to finish
        await asyncio.sleep(0.1)
        assert redis_data.get("lookup:repeat_key") == "repeated_db_value"

        # Reset mock call tracker
        mock_pers.get_app_setting.reset_mock()

        # Second read: Hits Redis directly, should NOT query SQLite
        val2 = await rm.get("lookup:repeat_key")
        assert val2 == "repeated_db_value"
        mock_pers.get_app_setting.assert_not_called()
    finally:
        await rm.close()


@pytest.mark.asyncio
async def test_lazy_cache_redis_recovery_no_rebuild() -> None:
    """Verify that after Redis recovery, the cache is NOT eagerly rebuilt (remains lazy)."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    rm.redis_provider.get = AsyncMock(return_value=None)
    rm.redis_provider.set = AsyncMock(return_value=None)

    # 1. Start in memory mode (Redis offline)
    rm.active_provider = rm.memory_provider
    rm.mode = "memory"
    rm.breaker_state = "OPEN"

    # Start monitor manually to simulate recovery
    # We will trigger the recovery logic directly by mocking ping to return True
    mock_pers = MagicMock()
    container.register(PersistenceProvider, lambda: mock_pers)

    # 2. Redis recovers
    await rm._poll_redis_recovery()

    # 3. Verify mode is back to redis, but we did NOT query persistence layer for any pre-population
    assert rm.mode == "redis"
    mock_pers.get_job.assert_not_called()
    mock_pers.get_active_schema.assert_not_called()
    mock_pers.get_app_setting.assert_not_called()

    await rm.close()


@pytest.mark.asyncio
async def test_lazy_cache_replay_expiry() -> None:
    """Verify that expired cache set events are filtered out and not replayed."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    rm.redis_provider.set = AsyncMock(return_value=None)

    await rm.initialize()
    rm.mode = "memory"
    rm.breaker_state = "OPEN"

    # Queue an event with TTL of 1 second
    await rm.set("schema:temp_key", "temp_value", expire=1)

    assert "schema:temp_key" in rm._pending_keys

    # Wait for the cache event to expire
    await asyncio.sleep(1.2)

    # Recover Redis
    rm.mode = "redis"

    # Let background task drain
    await asyncio.sleep(0.1)

    # Key should be skipped (not replayed) due to expiry
    assert "schema:temp_key" not in rm._pending_keys
    rm.redis_provider.set.assert_not_called()

    await rm.close()
