"""Custom exception classes for the LLM Gateway package."""

from typing import Any

from app.core.exceptions.exceptions import SeedOpsException


class LLMException(SeedOpsException):
    """Base exception class for all LLM Gateway exceptions."""

    provider_error_code: int | None = None
    provider_status: str | None = None
    provider_message: str | None = None

    def __init__(
        self,
        message: str,
        error_code: str = "LLM_GATEWAY_ERROR",
        recoverable: bool = False,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
        response_type: str | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Initialize LLMException."""
        self.response_type = response_type
        self.finish_reason = finish_reason
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        super().__init__(
            message=message,
            error_code=error_code,
            recoverable=recoverable,
            details=details,
            status_code=status_code,
        )


class LLMConfigurationError(LLMException):
    """Exception raised when LLM settings or API keys are missing/invalid."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize LLMConfigurationError."""
        super().__init__(
            message=message,
            error_code="LLM_CONFIG_ERROR",
            recoverable=False,
            details=details,
            status_code=500,
        )


class LLMProviderError(LLMException):
    """Exception raised when the LLM provider API returns a non-retryable error."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int = 500,
        recoverable: bool = False,
        response_type: str | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Initialize LLMProviderError."""
        super().__init__(
            message=message,
            error_code="LLM_PROVIDER_ERROR",
            recoverable=recoverable,
            details=details,
            status_code=status_code,
            response_type=response_type,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


class LLMTimeoutError(LLMException):
    """Exception raised when an LLM provider request times out."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        response_type: str | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Initialize LLMTimeoutError."""
        super().__init__(
            message=message,
            error_code="LLM_TIMEOUT_ERROR",
            recoverable=True,
            details=details,
            status_code=504,
            response_type=response_type,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


class LLMRateLimitError(LLMException):
    """Exception raised when the provider API returns a rate limit (429) error."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        response_type: str | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Initialize LLMRateLimitError."""
        super().__init__(
            message=message,
            error_code="LLM_RATE_LIMIT_ERROR",
            recoverable=True,
            details=details,
            status_code=429,
            response_type=response_type,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


class LLMValidationError(LLMException):
    """Exception raised when the response fails validation checks."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        recoverable: bool = True,
        response_type: str | None = None,
        finish_reason: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        """Initialize LLMValidationError."""
        super().__init__(
            message=message,
            error_code="LLM_VALIDATION_ERROR",
            recoverable=recoverable,
            details=details,
            status_code=500,
            response_type=response_type,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
