"""Custom exception classes for the Prompt Framework."""

from typing import Any

from app.core.exceptions.exceptions import SeedOpsException


class PromptException(SeedOpsException):
    """Base exception class for all Prompt Framework exceptions."""

    def __init__(
        self,
        message: str,
        error_code: str = "PROMPT_FRAMEWORK_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ) -> None:
        """Initialize PromptException."""
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=status_code,
        )


class PromptNotFoundError(PromptException):
    """Exception raised when a requested prompt template is not registered."""

    def __init__(self, name: str, version: str | None = None) -> None:
        """Initialize PromptNotFoundError."""
        super().__init__(
            message=f"Prompt template '{name}' (version: {version}) was not found.",
            error_code="PROMPT_NOT_FOUND",
            recoverable=False,
            details={"name": name, "version": version},
            status_code=404,
        )


class PromptTemplateError(PromptException):
    """Exception raised when prompt template parsing or rendering fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize PromptTemplateError."""
        super().__init__(
            message=message,
            error_code="PROMPT_TEMPLATE_ERROR",
            recoverable=False,
            details=details,
            status_code=500,
        )


class PromptValidationError(PromptException):
    """Exception raised when the rendered prompt fails validation checks."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize PromptValidationError."""
        super().__init__(
            message=message,
            error_code="PROMPT_VALIDATION_ERROR",
            recoverable=False,
            details=details,
            status_code=400,
        )
