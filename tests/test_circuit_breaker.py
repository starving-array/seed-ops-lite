import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.platform.runtime.manager import RuntimeManager


@pytest.mark.asyncio
async def test_circuit_breaker_flow() -> None:
    """Test standard Redis Circuit Breaker transition flows."""
    rm = RuntimeManager()
    rm.redis_provider = MagicMock()
    rm.redis_provider.ping = AsyncMock(return_value=True)
    rm.redis_provider.delete = AsyncMock(return_value=None)
    rm.redis_provider.set = AsyncMock(return_value=None)
    rm.redis_provider.sadd = AsyncMock(return_value=None)

    # 1. Initialize healthy -> CLOSED
    await rm.initialize()
    assert rm.breaker_state == "CLOSED"
    assert rm.mode == "redis"
    assert rm.failure_count == 0

    # 2. Redis read fails -> CLOSED to OPEN synchronously
    rm.redis_provider.get = AsyncMock(side_effect=Exception("Redis connection lost"))
    with patch(
        "app.platform.configuration.settings.platform_settings.RUNTIME_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        1,
    ):
        await rm.get("foo")
    assert rm.breaker_state == "OPEN"
    assert rm.mode == "memory"
    assert rm.failure_count == 1
    assert rm.last_failure_time is not None

    # 3. Trigger recovery check but fails -> stays OPEN
    rm.redis_provider.ping = AsyncMock(side_effect=Exception("Still unreachable"))
    with (
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS",
            0.01,
        ),
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_CIRCUIT_BREAKER_RECOVERY_SECONDS",
            0.01,
        ),
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_RECOVERY_POLL_INTERVAL_SECONDS",
            0.01,
        ),
    ):
        # Run loop in background task and cancel it to prevent hanging
        task = asyncio.create_task(rm._poll_redis_recovery())
        await asyncio.sleep(0.2)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Verify it stays OPEN and failure count increased
        assert rm.breaker_state == "OPEN"
        assert rm.failure_count >= 2

    # 4. Trigger recovery check succeeds -> CLOSED
    rm.redis_provider.ping = AsyncMock(return_value=True)
    with (
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_RECONNECT_INTERVAL_SECONDS",
            0.01,
        ),
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_CIRCUIT_BREAKER_RECOVERY_SECONDS",
            0.01,
        ),
        patch(
            "app.platform.configuration.settings.platform_settings.RUNTIME_RECOVERY_POLL_INTERVAL_SECONDS",
            0.01,
        ),
    ):
        # Manually kick recovery monitor (should complete successfully and exit the loop)
        rm.mode = "memory"  # Reset mode to enter loop
        await rm._poll_redis_recovery()
        assert rm.breaker_state == "CLOSED"
        assert rm.mode == "redis"
        assert rm.last_recovery_time is not None

    # Cleanup background worker task
    await rm.close()
