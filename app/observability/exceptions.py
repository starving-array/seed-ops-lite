"""Custom exceptions for the Observability module."""


class ObservabilityException(Exception):
    """Base exception for all Observability Engine errors."""

    pass


class MetricsCollectionException(ObservabilityException):
    """Raised when metrics collection or extraction fails."""

    pass
