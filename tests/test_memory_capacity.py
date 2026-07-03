import pytest

from app.platform.configuration.settings import platform_settings
from app.platform.providers.memory import MemoryRuntimeProvider


@pytest.mark.asyncio
async def test_memory_capacity_lru_eviction() -> None:
    """Verify capacity limit and LRU eviction order."""
    # Temporarily override settings
    orig_max = platform_settings.RUNTIME_MEMORY_CACHE_MAX_ENTRIES
    orig_batch = platform_settings.RUNTIME_MEMORY_EVICTION_BATCH_SIZE
    platform_settings.RUNTIME_MEMORY_CACHE_MAX_ENTRIES = 3
    platform_settings.RUNTIME_MEMORY_EVICTION_BATCH_SIZE = 1

    provider = MemoryRuntimeProvider()

    try:
        # Populate up to capacity
        await provider.set("key1", "val1")
        await provider.set("key2", "val2")
        await provider.set("key3", "val3")

        assert len(provider._lru_keys) == 3
        assert await provider.get("key1") == "val1"

        # Touch key1 to make it recently used (order should now be key2, key3, key1)
        # Verify get touches key1
        await provider.get("key1")

        # Exceed capacity
        await provider.set("key4", "val4")

        # key2 is the least recently used and should be evicted
        assert await provider.get("key2") is None
        assert await provider.get("key1") == "val1"
        assert await provider.get("key3") == "val3"
        assert await provider.get("key4") == "val4"
        assert provider.evicted_entries == 1

    finally:
        platform_settings.RUNTIME_MEMORY_CACHE_MAX_ENTRIES = orig_max
        platform_settings.RUNTIME_MEMORY_EVICTION_BATCH_SIZE = orig_batch


@pytest.mark.asyncio
async def test_memory_ttl_expiration_frees_capacity() -> None:
    """Verify TTL expiration and lazy cleanup free up space."""
    provider = MemoryRuntimeProvider()

    # Set key with 0 delay (immediate expiration)
    await provider.set("key_exp", "val", _expire=-1)

    # Lazy cleanup should trigger on get
    assert await provider.get("key_exp") is None
    assert "key_exp" not in provider._lru_keys
    assert provider.expired_entries_removed == 1


@pytest.mark.asyncio
async def test_memory_cleanup_correctness() -> None:
    """Verify full periodic cleanup removes all expired keys and updates metrics."""
    provider = MemoryRuntimeProvider()

    await provider.set("key_active", "val")
    await provider.set("key_expired", "val", _expire=-10)

    # Trigger manual periodic cleanup
    provider.run_periodic_cleanup()

    assert await provider.get("key_expired") is None
    assert await provider.get("key_active") == "val"
    assert provider.cleanup_runs == 1
    assert provider.last_cleanup is not None
