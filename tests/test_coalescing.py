import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.runtime.manager import RuntimeManager


@pytest.mark.asyncio
async def test_event_coalescing() -> None:
    """Test coalescing of duplicate events, newest wins, and metrics increments."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    rm.redis_provider.delete = AsyncMock(return_value=None)
    rm.redis_provider.set = AsyncMock(return_value=None)
    rm.redis_provider.push_to_queue = AsyncMock(return_value=None)

    # 1. Initialize healthy
    await rm.initialize()
    rm.mode = "redis"
    rm.breaker_state = "CLOSED"

    # 2. Pause worker processing by switching to memory mode internally (to queue items)
    rm.mode = "memory"

    # 3. Fire duplicate writes to the same key
    await rm.set("schema:5", "old_val")
    await rm.set("schema:5", "newest_val")
    await rm.set("schema:5", "final_val")

    # Verify coalesced state
    assert rm.coalesced_events == 2
    assert rm.unique_events == 1
    assert "schema:5" in rm._pending_keys

    # 4. Fire queue writes to assert payload coalescing
    await rm._execute_write("push_to_queue", "test_queue", "payload_1")
    await rm._execute_write("push_to_queue", "test_queue", "payload_2")

    assert rm.coalesced_events == 3
    assert rm.unique_events == 2
    assert "test_queue" in rm._pending_keys
    # Assert newest event won
    assert rm._pending_keys["test_queue"][2][0] == "payload_2"

    # 5. Recover and let worker process
    rm.mode = "redis"
    # Wait for background queue worker to drain
    await asyncio.sleep(0.1)

    # Verify processing complete
    assert "schema:5" not in rm._pending_keys
    assert "test_queue" not in rm._pending_keys
    assert rm.skipped_events == 0

    await rm.close()
