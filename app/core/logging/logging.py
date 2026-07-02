"""Structured logging configuration using structlog.

Environment-aware configuration:

* **development** (or ``LOG_PRETTY=True``):
  Routes all log output through ``PrettyConsoleFormatter``, which renders
  colour-coded, human-readable boxed log lines to stdout.

* **staging / production**:
  Uses ``structlog.processors.JSONRenderer`` for machine-parsable, log-
  aggregation-compatible JSON output.  Identical to the legacy behaviour.

The ``ExceptionDeduplicator`` is inserted into the processor chain in both
modes.  It ensures that when an exception bubbles up through several log
layers, only the innermost call emits the full traceback.

Backward compatibility
----------------------
All public names previously exported by this module (``add_correlation_id``,
``configure_logging``, ``correlation_id_ctx``, ``logger``) are preserved.
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.settings.config import settings
from app.telemetry.logger import StructuredLogger

# ---------------------------------------------------------------------------
# Legacy ContextVar — kept for backward-compatibility with the middleware layer
# ---------------------------------------------------------------------------
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


# ---------------------------------------------------------------------------
# Shared structlog processors
# ---------------------------------------------------------------------------


def add_correlation_id(
    _logger: Any, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Structlog processor to inject the correlation ID from context variables.

    Args:
        _logger: The logger instance.
        _method_name: The name of the logged method.
        event_dict: The current event dictionary.

    Returns:
        EventDict: The updated event dictionary containing the correlation ID if set.
    """
    # Try retrieving from unified ExecutionContext first
    from app.core.context.context import get_context

    ctx = get_context()
    if ctx.correlation_id:
        event_dict["correlation_id"] = ctx.correlation_id
    if ctx.request_id:
        event_dict["request_id"] = ctx.request_id
    if ctx.workflow_id:
        event_dict["workflow_id"] = ctx.workflow_id

    # Fallback to legacy ContextVar if not populated in modern context
    if "correlation_id" not in event_dict:
        correlation_id = correlation_id_ctx.get()
        if correlation_id:
            event_dict["correlation_id"] = correlation_id

    return event_dict


def _is_pretty_mode() -> bool:
    """Return True when the pretty dev console formatter should be active."""
    if settings.LOG_PRETTY:
        return True
    return settings.APP_ENV == "development"


def configure_logging() -> None:
    """Configure structlog and the standard library logging to route through structlog.

    Selects the appropriate output formatter based on the current environment:

    * ``development`` or ``LOG_PRETTY=True`` → ``PrettyConsoleFormatter``
    * All other environments → ``JSONRenderer`` (production-safe, aggregation-friendly)

    The ``ExceptionDeduplicator`` is always inserted into the chain so that
    duplicate stack traces are suppressed when exceptions propagate upward
    through multiple log-call layers.
    """
    from app.core.logging.formatters import (
        PrettyConsoleFormatter,
        exception_deduplicator,
    )

    # Processors shared by structlog and standard library logging
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_correlation_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        exception_deduplicator,  # deduplicate stack traces across log layers
    ]

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set up root logger handler
    handler = logging.StreamHandler(sys.stdout)

    pretty = _is_pretty_mode()

    # Production-grade logging formatters for stdlib routing:
    # ProcessorFormatter handles converting standard logging.LogRecord to structlog events.
    if pretty:
        formatter: logging.Formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=PrettyConsoleFormatter(),
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=(
                structlog.processors.JSONRenderer()
                if settings.LOG_JSON_FORMAT
                else structlog.dev.ConsoleRenderer()
            ),
        )

    handler.setFormatter(formatter)

    # Route standard library logs to structlog:
    # Use structlog.stdlib.LoggerFactory for stdlib logs
    logging.basicConfig(
        handlers=[handler],
        level=logging.INFO,
        force=True,  # Reset any existing default handlers
    )

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Clean and intercept logger handlers to redirect everything to the root handler
    # This prevents third-party packages from bypassing structlog's console formatter.
    for name in logging.root.manager.loggerDict:
        logger_obj = logging.getLogger(name)
        logger_obj.handlers = []
        logger_obj.propagate = True

    # Intercept all other loggers to propagate to root, use our formatter, and have NO separate handlers
    loggers_to_intercept = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "alembic",
        "sqlalchemy",
        "sqlalchemy.engine",
        "redis",
        "asyncio",
    ]
    for logger_name in loggers_to_intercept:
        child_logger = logging.getLogger(logger_name)
        child_logger.handlers = []
        child_logger.propagate = True
        child_logger.setLevel(log_level)

    # Reduce log noise from access logs specifically
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# Get structured logger instance
logger = StructuredLogger()
