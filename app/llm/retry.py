"""Configurable retry wrappers with exponential backoff and jitter for LLM calls."""

import asyncio
import secrets
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from app.core.settings.config import settings
from app.llm.exceptions import LLMException

T = TypeVar("T")


async def execute_with_retry(
    operation: Callable[[], Coroutine[Any, Any, T]],
    max_retries: int | None = None,
    base_delay_seconds: float = 1.0,
    max_delay_seconds: float = 8.0,
) -> T:
    """Execute an asynchronous operation with exponential backoff and jitter.

    Retries only on exceptions marked as recoverable (e.g. timeout, rate limits,
    transient server errors).

    Args:
        operation: No-arg callable returning an awaitable coroutine.
        max_retries: Max retry count overrides. Defaults to settings value.
        base_delay_seconds: Starting backoff multiplier.
        max_delay_seconds: Maximum ceiling for delay period.

    Returns:
        T: The successful operation result.

    Raises:
        Exception: The final raised exception if all attempts fail.
    """
    retries = max_retries if max_retries is not None else settings.LLM_MAX_RETRIES
    attempt = 0

    while True:
        try:
            return await operation()
        except Exception as exc:
            # Check if this exception is a recoverable LLMException
            is_recoverable = False
            if isinstance(exc, LLMException):
                is_recoverable = exc.recoverable
            elif isinstance(exc, asyncio.TimeoutError | ConnectionError | TimeoutError):
                is_recoverable = True

            if not is_recoverable or attempt >= retries:
                # Re-raise the exception if not retryable or max retries exceeded
                raise exc

            attempt += 1
            # Calculate backoff delay with jitter
            delay = min(base_delay_seconds * (2 ** (attempt - 1)), max_delay_seconds)
            jitter = secrets.SystemRandom().uniform(0, 0.2 * delay)
            sleep_time = delay + jitter

            # Circular import prevention: import logger inside the handler
            from app.core.logging.logging import logger
            from app.telemetry.events import EventID

            logger.warning(
                EventID.LOG_WARNING,
                f"LLM Gateway execution failed (Attempt {attempt}/{retries}). Retrying in {sleep_time:.2f}s...",
                component="LLMRetry",
                error=str(exc),
                attempt=attempt,
                max_retries=retries,
            )

            await asyncio.sleep(sleep_time)
