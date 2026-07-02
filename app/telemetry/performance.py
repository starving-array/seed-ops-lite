"""Performance instrumentation and LLM observability utilities.

Provides:

* ``PerformanceLogger`` — an async/sync context manager that measures
  wall-clock time for any named operation and automatically emits a
  ``PERF_SLOW_OPERATION`` warning when the elapsed time exceeds the
  configurable ``SLOW_LOG_THRESHOLD_MS`` setting.

* ``log_llm_observation`` — a convenience function that captures the
  full LLM metadata envelope (provider, model, tokens, latency, cost,
  finish reason, etc.) as a structured ``LLM_RESPONSE`` or ``LLM_ERROR``
  event, never inventing values for missing fields.
"""

from __future__ import annotations

import time
from contextlib import AbstractAsyncContextManager, AbstractContextManager
from types import TracebackType
from typing import Any

from app.telemetry.events import EventID

# ---------------------------------------------------------------------------
# Module-level logger — resolved lazily to avoid circular imports at load time
# but exposed as a module attribute so tests can patch it.
# ---------------------------------------------------------------------------


def _get_logger() -> Any:
    from app.core.logging.logging import logger as _logger

    return _logger


# Re-export as a module-level name so `patch("app.telemetry.performance.logger")`
# works in unit tests.  The actual value is set after the first import cycle
# completes; we use a lazy property via a wrapper object.
class _LazyLogger:
    """Thin wrapper that delegates every attribute access to the real logger."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_logger(), name)


logger: Any = _LazyLogger()


class PerformanceLogger(AbstractContextManager["PerformanceLogger"]):
    """Synchronous context manager for timing named operations.

    Emits ``PERF_SLOW_OPERATION`` at WARNING level if the elapsed time
    exceeds ``settings.SLOW_LOG_THRESHOLD_MS``.  Emits a DEBUG timing
    event for all operations so fast paths remain visible in debug mode.

    Example::

        with PerformanceLogger("sqlite.query", component="SQLiteProvider"):
            rows = await db.execute(stmt)

    Supported operation labels (for standardised SLOW_LOG_THRESHOLD_MS
    annotations)::

        sqlite  redis  llm  generation  export  validation  migration  health
    """

    def __init__(
        self,
        operation: str,
        *,
        component: str | None = None,
        threshold_ms: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.operation = operation
        self.component = component
        self.extra = extra or {}
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

        # Defer settings import to avoid circular dependencies at module load
        if threshold_ms is not None:
            self._threshold_ms: float = threshold_ms
        else:
            from app.core.settings.config import settings as _s

            self._threshold_ms = _s.SLOW_LOG_THRESHOLD_MS

    # ------------------------------------------------------------------
    # Synchronous context manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> PerformanceLogger:
        self._start = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000.0
        self._emit()

    def _emit(self) -> None:
        """Emit the appropriate log event after timing completes."""
        payload: dict[str, Any] = {
            "operation": self.operation,
            "duration_ms": round(self.elapsed_ms, 2),
            **self.extra,
        }
        if self.component:
            payload["component"] = self.component

        if self.elapsed_ms >= self._threshold_ms:
            logger.warning(
                EventID.PERF_SLOW_OPERATION,
                f"Slow operation detected: {self.operation} took {self.elapsed_ms:.1f} ms "
                f"(threshold={self._threshold_ms:.0f} ms)",
                **payload,
            )
        else:
            logger.debug(
                EventID.LOG_INFO,
                f"Operation completed: {self.operation}",
                **payload,
            )


class AsyncPerformanceLogger(AbstractAsyncContextManager["AsyncPerformanceLogger"]):
    """Async context manager variant of ``PerformanceLogger``.

    Example::

        async with AsyncPerformanceLogger("llm.generate", component="LLMGateway"):
            response = await gateway.generate(request)
    """

    def __init__(
        self,
        operation: str,
        *,
        component: str | None = None,
        threshold_ms: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._sync = PerformanceLogger(
            operation,
            component=component,
            threshold_ms=threshold_ms,
            extra=extra,
        )
        self.elapsed_ms: float = 0.0

    async def __aenter__(self) -> AsyncPerformanceLogger:
        self._sync.__enter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._sync.__exit__(exc_type, exc_val, exc_tb)
        self.elapsed_ms = self._sync.elapsed_ms


def log_llm_observation(
    *,
    success: bool,
    provider: str | None = None,
    model: str | None = None,
    workflow_id: str | None = None,
    table: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    thinking_tokens: int | None = None,
    cached_tokens: int | None = None,
    total_tokens: int | None = None,
    latency_ms: float | None = None,
    retry_count: int | None = None,
    http_status: int | None = None,
    finish_reason: str | None = None,
    estimated_cost: float | None = None,
    error: str | None = None,
    component: str = "LLMGateway",
) -> None:
    """Emit a structured LLM observability log entry.

    Only fields that are actually provided are included in the log payload —
    missing values are *never* invented or defaulted to zero.

    Args:
        success: Whether the LLM call succeeded.
        provider: API provider name (e.g. ``"Google"``).
        model: Model identifier (e.g. ``"gemini-1.5-pro"``).
        workflow_id: Active workflow/generation run identifier.
        table: Schema table being generated (if applicable).
        prompt_tokens: Token count of the input prompt.
        completion_tokens: Token count of the generated completion.
        thinking_tokens: Reasoning/thinking token count (Gemini-specific).
        cached_tokens: Cache-hit token count.
        total_tokens: Total token count (prompt + completion + thinking).
        latency_ms: End-to-end API latency in milliseconds.
        retry_count: Number of retries attempted.
        http_status: HTTP status code returned by the provider.
        finish_reason: Model finish reason (``"STOP"``, ``"MAX_TOKENS"`` etc.).
        estimated_cost: Estimated monetary cost in USD.
        error: Error message when ``success=False``.
        component: Logger component label.
    """
    # Build payload — only include fields that are actually present
    payload: dict[str, Any] = {}

    def _add(key: str, val: Any) -> None:
        if val is not None:
            payload[key] = val

    _add("provider", provider)
    _add("model", model)
    _add("workflow_id", workflow_id)
    _add("table", table)
    _add("prompt_tokens", prompt_tokens)
    _add("completion_tokens", completion_tokens)
    _add("thinking_tokens", thinking_tokens)
    _add("cached_tokens", cached_tokens)
    _add("total_tokens", total_tokens)
    _add("latency_ms", round(latency_ms, 2) if latency_ms is not None else None)
    _add("retry_count", retry_count)
    _add("http_status", http_status)
    _add("finish_reason", finish_reason)
    _add("estimated_cost", estimated_cost)
    _add("error", error)

    if success:
        logger.info(
            EventID.LLM_RESPONSE,
            "LLM API request succeeded",
            component=component,
            **payload,
        )
    else:
        logger.error(
            EventID.LLM_ERROR,
            f"LLM API request failed: {error or 'unknown error'}",
            component=component,
            **payload,
        )
