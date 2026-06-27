"""Structured enterprise log wrapper enforcing context schema and event cataloging."""

from typing import Any

import structlog

from app.core.context.context import get_context
from app.core.settings.config import settings
from app.telemetry.events import EventID


class StructuredLogger:
    """Wrapper around structlog to enforce standardized logging schema."""

    def __init__(self, name: str | None = None) -> None:
        """Initialize StructuredLogger.

        Args:
            name: Optional logger name channel.
        """
        self._logger = structlog.get_logger(name)

    def _log(
        self,
        level: str,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Core logging engine building standard payload from ExecutionContext."""
        # Retrieve context from thread/async local ExecutionContext
        ctx = get_context()

        # Build standardized enterprise log context payload
        log_payload = {
            "event_id": str(event_id),
            "request_id": ctx.request_id,
            "correlation_id": ctx.correlation_id,
            "trace_id": ctx.trace_id,
            "component": component or ctx.worker_id or "core",
            "phase": ctx.phase_name,
            "duration_ms": duration_ms,
            "environment": settings.APP_ENV,
            **kwargs,
        }

        # Filter out keys with None values to maintain clean serialization
        cleaned_payload = {k: v for k, v in log_payload.items() if v is not None}

        # Route log statement to underlying structlog logger
        log_method = getattr(self._logger, level)
        log_method(message, **cleaned_payload)

    def info(
        self,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log structured message at INFO level."""
        self._log(
            "info",
            event_id,
            message,
            duration_ms=duration_ms,
            component=component,
            **kwargs,
        )

    def warning(
        self,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log structured message at WARNING level."""
        self._log(
            "warning",
            event_id,
            message,
            duration_ms=duration_ms,
            component=component,
            **kwargs,
        )

    def error(
        self,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log structured message at ERROR level."""
        self._log(
            "error",
            event_id,
            message,
            duration_ms=duration_ms,
            component=component,
            **kwargs,
        )

    def exception(
        self,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log structured message with exception details at ERROR level."""
        self._log(
            "exception",
            event_id,
            message,
            duration_ms=duration_ms,
            component=component,
            **kwargs,
        )

    def critical(
        self,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log structured message at CRITICAL level."""
        self._log(
            "critical",
            event_id,
            message,
            duration_ms=duration_ms,
            component=component,
            **kwargs,
        )

    def debug(
        self,
        event_id: EventID | str,
        message: str,
        duration_ms: float | None = None,
        component: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Log structured message at DEBUG level."""
        self._log(
            "debug",
            event_id,
            message,
            duration_ms=duration_ms,
            component=component,
            **kwargs,
        )


# Global default structured logger instance
logger = StructuredLogger()
