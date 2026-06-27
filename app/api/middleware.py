"""Proxy for api/middleware.py backward compatibility."""

from app.core.middleware.middleware import (
    CorrelationIdMiddleware,
    ExceptionLoggingMiddleware,
)

__all__ = [
    "CorrelationIdMiddleware",
    "ExceptionLoggingMiddleware",
]
