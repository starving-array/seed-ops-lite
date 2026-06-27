"""Structured JSON logging configuration using structlog."""

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from app.core.settings.config import settings
from app.telemetry.logger import StructuredLogger

# ContextVar to store correlation ID and other request-scoped details
correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)


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

    # Fallback to legacy ContextVar if not populated in modern context
    if "correlation_id" not in event_dict:
        correlation_id = correlation_id_ctx.get()
        if correlation_id:
            event_dict["correlation_id"] = correlation_id

    return event_dict


def configure_logging() -> None:
    """Configures structlog and standard logging to route through structlog."""
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
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set up root logger handler
    handler = logging.StreamHandler(sys.stdout)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_processors=shared_processors,
        processor=(
            structlog.processors.JSONRenderer()
            if settings.LOG_JSON_FORMAT
            else structlog.dev.ConsoleRenderer()
        ),
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    root_logger.setLevel(log_level)

    # Reduce log noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


# Get structured logger instance
logger = StructuredLogger()
