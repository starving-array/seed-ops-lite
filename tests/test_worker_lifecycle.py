import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.endpoints.health import RuntimeStatus
from app.platform.runtime.manager import RuntimeManager


@pytest.mark.asyncio
async def test_worker_lifecycle_startup_and_shutdown() -> None:
    """Verify clean startup, worker running, uptime tracking, and clean shutdown."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)

    # 1. Before startup
    assert rm._worker_task is None
    assert rm.worker_uptime == 0.0

    # 2. Startup
    await rm.initialize()
    assert rm._worker_task is not None
    assert not rm._worker_task.done()

    # Verify uptime is tracked and positive
    await asyncio.sleep(0.1)
    uptime1 = rm.worker_uptime
    assert uptime1 > 0.0

    # 3. Shutdown
    await rm.close()
    assert rm._worker_task is None
    assert rm.worker_uptime == 0.0
    assert rm._monitor_task is None


@pytest.mark.asyncio
async def test_worker_lifecycle_duplicate_prevention() -> None:
    """Verify that multiple startups do not spawn duplicate sync worker or recovery monitor tasks."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=False)  # Trigger monitor startup

    # Initialize once
    await rm.initialize()
    worker_1 = rm._worker_task
    monitor_1 = rm._monitor_task

    assert worker_1 is not None
    assert monitor_1 is not None

    # Call initialize again
    await rm.initialize()

    # Ensure they are the exact same task instances (not duplicated)
    assert rm._worker_task is worker_1
    assert rm._monitor_task is monitor_1

    # Call start_recovery_monitor again
    rm.start_recovery_monitor()
    assert rm._monitor_task is monitor_1

    await rm.close()


@pytest.mark.asyncio
async def test_worker_lifecycle_metrics_collection() -> None:
    """Verify Average Sync Time metric calculation and metrics exposure."""
    rm = RuntimeManager()

    # Setup mock with delayed ping/set to record measurable sync time
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)

    async def slow_set(*_args, **_kwargs):
        await asyncio.sleep(0.05)

    async def slow_delete(*_args, **_kwargs):
        await asyncio.sleep(0.05)

    rm.redis_provider.set = AsyncMock(side_effect=slow_set)
    rm.redis_provider.delete = AsyncMock(side_effect=slow_delete)

    # Start manager in memory mode to queue event
    await rm.initialize()
    rm.mode = "memory"

    # Queue an event
    await rm.set("schema:metric_test", "value")

    # Recover Redis to trigger worker sync processing
    rm.mode = "redis"

    # Wait for queue worker to process the set event
    await asyncio.sleep(0.15)

    # Check metrics
    assert rm._total_sync_count == 1
    assert rm._total_sync_time >= 0.04
    assert rm.average_sync_time >= 0.04

    # Verify Pydantic model serialization for diagnostics API
    status = RuntimeStatus(
        provider="RedisRuntimeProvider",
        redis_status="healthy",
        connection_status="connected",
        reconnect_count=rm.reconnect_count,
        mode=rm.mode,
        queue_size=0,
        queue_capacity=100,
        dropped_events=rm.dropped_events,
        queue_utilization=0.0,
        coalesced_events=rm.coalesced_events,
        unique_events=rm.unique_events,
        skipped_events=rm.skipped_events,
        worker_uptime_seconds=rm.worker_uptime,
        average_sync_time_seconds=rm.average_sync_time,
    )

    assert status.worker_uptime_seconds > 0.0
    assert status.average_sync_time_seconds >= 0.04

    await rm.close()
