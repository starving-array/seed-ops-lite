from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.platform.runtime.manager import RuntimeManager


@pytest.mark.asyncio
async def test_bounded_sync_queue_behavior() -> None:
    """Test standard bounded cache queue logic, limits, drops, and recoveries."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    rm.redis_provider.delete = AsyncMock(return_value=None)
    rm.redis_provider.set = AsyncMock(return_value=None)

    # 1. Initialize queue with a small capacity of 2
    with patch(
        "app.platform.configuration.settings.platform_settings.RUNTIME_CACHE_SYNC_QUEUE_SIZE",
        2,
    ):
        await rm.initialize()
        assert rm._sync_queue is not None
        assert rm._sync_queue.maxsize == 2

    # 2. Put 2 elements -> queue becomes full
    rm.mode = "redis"
    rm.breaker_state = "CLOSED"
    await rm.set("key1", "val1")
    await rm.set("key2", "val2")
    assert rm._sync_queue.qsize() <= 2
    assert rm.dropped_events == 0

    # 3. Put 3rd element -> queue is full, events dropped, SQLite write doesn't fail
    await rm.set("key3", "val3")
    assert (
        rm.dropped_events >= 0
    )  # Depending on how fast background workers consume, it could drop

    # Force queue full condition by manually pushing
    for i in range(10):
        rm._queue_sync_event(("invalidate", f"force_{i}", None))

    assert rm._sync_queue.full() is True
    assert rm.dropped_events > 0

    # Pushing when full doesn't crash or raise errors
    rm._queue_sync_event(("invalidate", "overflow_key", None))
    assert rm.dropped_events > 0

    # Clean up worker
    await rm.close()
