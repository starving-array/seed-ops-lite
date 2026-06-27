"""Proxy for core/exceptions.py backward compatibility."""

from app.core.exceptions.exceptions import (
    ConfigurationError,
    ConfigurationException,
    DatabaseConnectionError,
    RedisConnectionException,
    ResourceNotFoundError,
    SeedOpsError,
    SeedOpsException,
    StorageTimeoutError,
    ValidationException,
)

__all__ = [
    "ConfigurationError",
    "ConfigurationException",
    "DatabaseConnectionError",
    "RedisConnectionException",
    "ResourceNotFoundError",
    "SeedOpsError",
    "SeedOpsException",
    "StorageTimeoutError",
    "ValidationException",
]
