"""Retry logic and execution retry policies for workflow tasks."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class RetryPolicy:
    """Exponential backoff execution wrapper implementing retry thresholds."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay_seconds: float = 0.1,
        backoff_factor: float = 2.0,
    ) -> None:
        """Initialize RetryPolicy.

        Args:
            max_retries: Max retry attempts count.
            base_delay_seconds: Starting backoff wait duration in seconds.
            backoff_factor: Multiplier applied per backoff iteration.
        """
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.backoff_factor = backoff_factor

    async def execute_with_retry(
        self,
        func: Callable[[], Awaitable[Any]],
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> Any:
        """Execute an asynchronous callback wrapper applying configured retry rules.

        Args:
            func: Target asynchronous operation callback.
            on_retry: Optional callback hook triggered on retry attempts.

        Returns:
            Any: Outcome from function execution.

        Raises:
            Exception: Last caught execution error after exhaustion of attempts.
        """
        attempt = 0
        while True:
            try:
                return await func()
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise exc

                attempt += 1
                delay = self.base_delay_seconds * (self.backoff_factor ** (attempt - 1))
                if on_retry:
                    on_retry(attempt, exc)

                # Use non-blocking sleep
                await asyncio.sleep(delay)
