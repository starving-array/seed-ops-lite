"""Proxy for core/logging.py backward compatibility."""

from app.core.logging.logging import (
    add_correlation_id,
    configure_logging,
    correlation_id_ctx,
    logger,
)

__all__ = [
    "add_correlation_id",
    "configure_logging",
    "correlation_id_ctx",
    "logger",
]
