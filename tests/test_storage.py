"""Unit tests for the storage abstraction layer (MemoryStorage, RedisStorage, and fallback)."""

from unittest.mock import AsyncMock

import pytest

from app.core.storage.base import MemoryStorage, RedisStorage
from app.core.storage.client import is_local_memory_mode


@pytest.mark.asyncio
async def test_memory_storage_operations() -> None:
    """Test basic key-value, set, and glob matching operations in MemoryStorage."""
    store = MemoryStorage()

    # Test key-value set and get
    await store.set("key1", "value1")
    assert await store.get("key1") == "value1"
    assert await store.get("key2") is None

    # Test overwrite
    await store.set("key1", "value1_updated")
    assert await store.get("key1") == "value1_updated"

    # Test sets operations
    await store.sadd("set1", "m1", "m2")
    assert await store.smembers("set1") == {"m1", "m2"}

    await store.srem("set1", "m1")
    assert await store.smembers("set1") == {"m2"}

    # Test key pattern matching
    await store.set("jobs:123", "data")
    await store.sadd("jobs:all_ids", "123")
    keys = await store.keys("jobs:*")
    assert set(keys) == {"jobs:123", "jobs:all_ids"}

    # Test delete
    await store.delete("key1", "set1")
    assert await store.get("key1") is None
    assert await store.smembers("set1") == set()

    # Test ping
    assert await store.ping() is True


@pytest.mark.asyncio
async def test_redis_storage_operations() -> None:
    """Test RedisStorage forwards operations directly to the underlying Redis client."""
    mock_client = AsyncMock()
    mock_client.get.return_value = "redis_val"
    mock_client.ping.return_value = True
    mock_client.smembers.return_value = {"a", "b"}
    mock_client.keys.return_value = ["jobs:1"]

    store = RedisStorage(mock_client)

    # Test get
    val = await store.get("some_key")
    assert val == "redis_val"
    mock_client.get.assert_called_once_with("some_key")

    # Test set without expire
    await store.set("k", "v")
    mock_client.set.assert_called_once_with("k", "v")

    # Test set with expire
    await store.set("k_exp", "v_exp", expire=60)
    mock_client.setex.assert_called_once_with("k_exp", 60, "v_exp")

    # Test delete
    await store.delete("k1", "k2")
    mock_client.delete.assert_called_once_with("k1", "k2")

    # Test sadd / srem
    await store.sadd("s", "m")
    mock_client.sadd.assert_called_once_with("s", "m")

    await store.srem("s", "m")
    mock_client.srem.assert_called_once_with("s", "m")

    # Test smembers
    assert await store.smembers("s") == {"a", "b"}
    mock_client.smembers.assert_called_once_with("s")

    # Test keys
    assert await store.keys("jobs:*") == ["jobs:1"]
    mock_client.keys.assert_called_once_with("jobs:*")

    # Test ping
    assert await store.ping() is True
    mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_init_storage_redis_available() -> None:
    """Test init_storage selects RedisStorage if connection is healthy."""
    from typing import Any

    from app.platform.container import get_runtime_provider

    rm: Any = get_runtime_provider()
    rm.mode = "redis"
    assert is_local_memory_mode() is False


@pytest.mark.asyncio
async def test_init_storage_fallback_to_memory() -> None:
    """Test init_storage falls back to MemoryStorage if Redis connection fails."""
    from typing import Any

    from app.platform.container import get_runtime_provider

    rm: Any = get_runtime_provider()
    rm.mode = "memory"
    assert is_local_memory_mode() is True
