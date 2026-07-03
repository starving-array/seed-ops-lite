from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.container import container, get_runtime_provider
from app.platform.runtime.interfaces import RuntimeProvider
from app.platform.runtime.manager import runtime_manager


@pytest.mark.asyncio
async def test_get_runtime_provider_returns_singleton() -> None:
    """Verify multiple calls to get_runtime_provider return the exact same instance."""
    rm1 = get_runtime_provider()
    rm2 = get_runtime_provider()

    assert rm1 is rm2
    assert id(rm1) == id(rm2)
    assert rm1 is runtime_manager


@pytest.mark.asyncio
async def test_runtime_manager_worker_and_monitor_singletons() -> None:
    """Verify that worker and recovery monitor tasks do not duplicate under multiple initializations."""
    rm = get_runtime_provider()

    # Mock low-level Redis interactions to avoid actual networking in tests
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)

    # Save original tasks if active
    orig_worker = rm._worker_task
    orig_monitor = rm._monitor_task

    try:
        # Multiple initializations
        await rm.initialize()
        await rm.initialize()

        # Verify worker and monitor task counts
        w1 = rm._worker_task
        m1 = rm._monitor_task

        await rm.initialize()

        assert rm._worker_task is w1
        assert rm._monitor_task is m1

    finally:
        # Restore state or close
        if rm._worker_task and rm._worker_task != orig_worker:
            rm._worker_task.cancel()
        if rm._monitor_task and rm._monitor_task != orig_monitor:
            rm._monitor_task.cancel()


@pytest.mark.asyncio
async def test_runtime_manager_shared_state() -> None:
    """Verify that all consumers of RuntimeProvider share queue, mode, and breaker states."""
    rm1 = get_runtime_provider()

    # Modify state via container lookup
    rm_resolved = (
        container.get(RuntimeProvider)
        if RuntimeProvider in container._providers
        else get_runtime_provider()
    )

    orig_mode = rm_resolved.mode
    orig_breaker = rm_resolved.breaker_state
    orig_queue = rm_resolved._sync_queue

    try:
        # Modify instance attributes on resolved instance
        rm_resolved.mode = "test_custom_mode"
        rm_resolved.breaker_state = "HALF_OPEN"

        # Verify changes are reflected globally on get_runtime_provider()
        assert rm1.mode == "test_custom_mode"
        assert rm1.breaker_state == "HALF_OPEN"
        assert rm1._sync_queue is orig_queue
    finally:
        rm_resolved.mode = orig_mode
        rm_resolved.breaker_state = orig_breaker
