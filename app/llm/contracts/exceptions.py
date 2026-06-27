"""Custom exception classes for contract validation and parsing errors."""

from typing import Any


class AIContractError(Exception):
    """Base exception for all AI contract errors."""

    def __init__(self, message: str, is_retryable: bool = False) -> None:
        """Initialize AIContractError.

        Args:
            message: Description of the failure.
            is_retryable: Boolean flag marking error as transient/retryable.
        """
        super().__init__(message)
        self.is_retryable = is_retryable


class AIContractParsingError(AIContractError):
    """Raised when raw response cannot be parsed as JSON or expected structure."""

    def __init__(self, message: str) -> None:
        """Initialize AIContractParsingError.

        Args:
            message: Details of parsing failure.
        """
        super().__init__(message, is_retryable=False)


class AIContractValidationError(AIContractError):
    """Raised when the parsed JSON fails Pydantic schema validation."""

    def __init__(
        self, message: str, errors: list[dict[str, Any]] | None = None
    ) -> None:
        """Initialize AIContractValidationError.

        Args:
            message: Details of validation failure.
            errors: Underlying validation issues from Pydantic.
        """
        super().__init__(message, is_retryable=False)
        self.errors = errors or []


class AIContractProviderError(AIContractError):
    """Raised when the gateway or provider returns an error."""

    def __init__(self, message: str, is_retryable: bool = True) -> None:
        """Initialize AIContractProviderError.

        Args:
            message: Provider error description.
            is_retryable: Indicates if execution can be retried.
        """
        super().__init__(message, is_retryable=is_retryable)
