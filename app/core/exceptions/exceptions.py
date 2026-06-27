"""Custom exception classes for the SeedOps Lite application."""

from typing import Any


class SeedOpsException(Exception):
    """Base exception class for all SeedOps Lite exceptions.

    Attributes:
        message: The detailed description of the error.
        error_code: Unique system-level error string identifier.
        recoverable: Flag indicating if the operation can be retried.
        details: Structural details or dictionary containing error metadata.
        status_code: The corresponding HTTP status code mapping.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_SERVER_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        """Initialize SeedOpsException.

        Args:
            message: Description of the error.
            error_code: String code identifying the error family.
            recoverable: Boolean indicating retry availability.
            details: Optional metadata dict.
            status_code: HTTP response status code.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.recoverable = recoverable
        self.details = details or {}
        self.status_code = status_code


class ConfigurationException(SeedOpsException):
    """Exception raised when system configurations are invalid or missing."""

    def __init__(
        self,
        message: str,
        error_code: str = "CONFIGURATION_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ConfigurationException."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=500,
        )


class RedisConnectionException(SeedOpsException):
    """Exception raised when database/caching connections fail."""

    def __init__(
        self,
        message: str,
        error_code: str = "REDIS_CONNECTION_ERROR",
        recoverable: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize RedisConnectionException."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=503,
        )


class ValidationException(SeedOpsException):
    """Exception raised when incoming payloads or schemas fail validation."""

    def __init__(
        self,
        message: str,
        error_code: str = "VALIDATION_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize ValidationException."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=422,
        )


# ==============================================================================
# Backward Compatibility Layer (Legacy Exceptions)
# ==============================================================================


class SeedOpsError(SeedOpsException):
    """Legacy base error class, mapping to SeedOpsException."""

    def __init__(
        self,
        message: str,
        error_code: str = "LEGACY_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        """Initialize legacy SeedOpsError."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=status_code,
        )


class DatabaseConnectionError(RedisConnectionException):
    """Legacy DatabaseConnectionError, mapping to RedisConnectionException."""

    def __init__(
        self,
        message: str,
        error_code: str = "REDIS_CONNECTION_ERROR",
        recoverable: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize legacy DatabaseConnectionError with status code 503."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
        )


class StorageTimeoutError(SeedOpsException):
    """Legacy StorageTimeoutError, mapping to SeedOpsException."""

    def __init__(
        self,
        message: str,
        error_code: str = "STORAGE_TIMEOUT_ERROR",
        recoverable: bool = True,
        details: dict[str, Any] | None = None,
        status_code: int = 504,
    ) -> None:
        """Initialize legacy StorageTimeoutError with status code 504."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=status_code,
        )


class ConfigurationError(ConfigurationException):
    """Legacy ConfigurationError, mapping to ConfigurationException."""

    def __init__(
        self,
        message: str,
        error_code: str = "CONFIGURATION_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize legacy ConfigurationError with status code 500."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
        )


class ResourceNotFoundError(SeedOpsException):
    """Legacy ResourceNotFoundError, mapping to SeedOpsException."""

    def __init__(
        self,
        message: str,
        error_code: str = "RESOURCE_NOT_FOUND_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
        status_code: int = 404,
    ) -> None:
        """Initialize legacy ResourceNotFoundError with status code 404."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=status_code,
        )
