"""Orchestrator normalizer parsing, validating, and classifying LLM responses."""

import asyncio
from typing import Any

from app.core.context.context import get_context
from app.core.logging.logging import logger
from app.llm.contracts.base import T
from app.llm.contracts.exceptions import (
    AIContractParsingError,
    AIContractProviderError,
    AIContractValidationError,
)
from app.llm.contracts.parser import parse_to_dict
from app.llm.contracts.request import AIContractRequest
from app.llm.contracts.response import (
    AIContractResponse,
    ContractErrorDetails,
    ContractMetadata,
)
from app.llm.contracts.validator import validate_schema
from app.llm.exceptions import LLMException, LLMValidationError
from app.llm.gateway import LLMGateway
from app.llm.models import LLMRequest, LLMResponse
from app.prompts.models import RenderedPrompt
from app.telemetry.events import EventID


class AIContractNormalizer:
    """Orchestrates parsing, validation, and normalization of LLM responses against contracts."""

    @staticmethod
    def normalize_success(
        response: LLMResponse,
        request: AIContractRequest[T],
        validated_data: T,
    ) -> AIContractResponse[T]:
        """Normalize a successful LLM interaction into a consistent AIContractResponse.

        Args:
            response: Standard gateway LLMResponse.
            request: Standard contract request container.
            validated_data: Validated Pydantic model instance.

        Returns:
            AIContractResponse[T]: Consistent, structured successful result.
        """
        finish_reason = None
        if response.raw_response:
            candidates = response.raw_response.get("candidates", [])
            if candidates:
                finish_reason = candidates[0].get("finishReason")

        prompt_hash = None
        prompt_version = None
        if isinstance(request.prompt, RenderedPrompt):
            prompt_hash = request.prompt.prompt_hash
            prompt_version = request.prompt.template_version

        metadata = ContractMetadata(
            request_id=response.request_id,
            correlation_id=response.correlation_id,
            provider=response.usage.provider,
            model=response.usage.model,
            prompt_hash=prompt_hash,
            prompt_version=prompt_version,
            latency_ms=response.usage.latency_ms,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            estimated_cost=response.usage.estimated_cost,
            finish_reason=finish_reason,
        )

        return AIContractResponse(
            success=True, data=validated_data, error=None, metadata=metadata
        )

    @staticmethod
    def normalize_failure(
        exc: Exception,
        request: AIContractRequest[T],
        response: LLMResponse | None = None,
    ) -> AIContractResponse[T]:
        """Normalize a failed LLM interaction or contract validation into a consistent AIContractResponse.

        Args:
            exc: Exception that caused the execution or validation to fail.
            request: Standard contract request container.
            response: Optional LLMResponse if failure occurred after gateway returned content.

        Returns:
            AIContractResponse[T]: Consistent, structured failed result with classified details.
        """
        error_type = "unknown"
        is_retryable = False
        raw_details: dict[str, Any] = {}
        message = str(exc)

        details = getattr(exc, "details", None) or {}
        cause = getattr(exc, "__cause__", None)
        if cause and not details:
            details = getattr(cause, "details", None) or {}

        if isinstance(exc, AIContractValidationError):
            error_type = "validation"
            is_retryable = False
            raw_details = {"errors": exc.errors}
        elif "errors" in details and details["errors"] is not None:
            error_type = "validation"
            is_retryable = False
            raw_details = {"errors": details["errors"]}
        elif isinstance(exc, AIContractParsingError | LLMValidationError):
            error_type = "parsing"
            is_retryable = False
        elif isinstance(exc, AIContractProviderError):
            error_type = "provider"
            is_retryable = exc.is_retryable
        elif isinstance(exc, LLMException):
            error_type = "provider"
            is_retryable = exc.recoverable
            raw_details = getattr(exc, "details", {}) or {}
        elif isinstance(exc, asyncio.TimeoutError | ConnectionError | TimeoutError):
            error_type = "provider"
            is_retryable = True
        else:
            error_type = "system"
            is_retryable = False

        error_details = ContractErrorDetails(
            message=message,
            error_type=error_type,
            is_retryable=is_retryable,
            raw_details=raw_details,
        )

        if response:
            finish_reason = None
            if response.raw_response:
                candidates = response.raw_response.get("candidates", [])
                if candidates:
                    finish_reason = candidates[0].get("finishReason")

            prompt_hash = None
            prompt_version = None
            if isinstance(request.prompt, RenderedPrompt):
                prompt_hash = request.prompt.prompt_hash
                prompt_version = request.prompt.template_version

            metadata = ContractMetadata(
                request_id=response.request_id,
                correlation_id=response.correlation_id,
                provider=response.usage.provider,
                model=response.usage.model,
                prompt_hash=prompt_hash,
                prompt_version=prompt_version,
                latency_ms=response.usage.latency_ms,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                estimated_cost=response.usage.estimated_cost,
                finish_reason=finish_reason,
            )
        else:
            prompt_hash = None
            prompt_version = None
            provider = "Google"
            model = "unknown"
            if isinstance(request.prompt, RenderedPrompt):
                prompt_hash = request.prompt.prompt_hash
                prompt_version = request.prompt.template_version
                provider = request.prompt.provider or "Google"
                model = request.prompt.model or "unknown"
            elif isinstance(request.prompt, LLMRequest):
                model = request.prompt.model or "unknown"

            ctx = get_context()
            metadata = ContractMetadata(
                request_id=None,
                correlation_id=ctx.correlation_id,
                provider=provider,
                model=model,
                prompt_hash=prompt_hash,
                prompt_version=prompt_version,
                latency_ms=0.0,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost=0.0,
                finish_reason=None,
            )

        return AIContractResponse(
            success=False, data=None, error=error_details, metadata=metadata
        )

    @staticmethod
    async def execute_contract(
        gateway: LLMGateway,
        contract_request: AIContractRequest[T],
    ) -> AIContractResponse[T]:
        """Execute the contract request against LLMGateway, parse, validate, and normalize the output.

        Args:
            gateway: LLM gateway client responsible for model execution.
            contract_request: Structured request wrapping input prompt and response schema.

        Returns:
            AIContractResponse[T]: Standardized success or failure wrapper.
        """
        response = None
        try:
            validated_data_container: dict[str, Any] = {}

            def validate_resp(resp: LLMResponse) -> None:
                try:
                    parsed_dict = parse_to_dict(resp.text)
                    val_data = validate_schema(
                        parsed_dict, contract_request.response_schema
                    )
                    validated_data_container["data"] = val_data
                except Exception as ve:
                    # Raise LLMValidationError to trigger gateway retry loop
                    from app.llm.exceptions import LLMValidationError

                    errors = getattr(ve, "errors", None)
                    if errors and callable(errors):
                        try:
                            errors = errors()
                        except Exception:
                            errors = None
                    details = {"errors": errors} if errors else None

                    raise LLMValidationError(
                        message=f"Contract structural validation failed: {ve}",
                        details=details,
                    ) from ve

            response = await gateway.generate(
                contract_request.prompt,
                json_mode=contract_request.json_mode,
                validator_callback=validate_resp,
            )

            validated_data = validated_data_container["data"]

            # Telemetry logging for success
            logger.info(
                EventID.LOG_INFO,
                "AI Contract executed and validated successfully",
                component="AIContract",
                schema=contract_request.response_schema.__name__,
                request_id=response.request_id,
                correlation_id=response.correlation_id,
            )

            return AIContractNormalizer.normalize_success(
                response=response,
                request=contract_request,
                validated_data=validated_data,
            )

        except Exception as exc:
            # Classify custom exceptions or wrap existing provider/system errors
            wrapped_exc = exc
            if isinstance(exc, LLMValidationError):
                details = getattr(exc, "details", None) or {}
                if "errors" in details and details["errors"] is not None:
                    wrapped_exc = AIContractValidationError(
                        str(exc), errors=details["errors"]
                    )
                else:
                    wrapped_exc = AIContractParsingError(str(exc))
            elif isinstance(exc, LLMException):
                wrapped_exc = AIContractProviderError(
                    str(exc), is_retryable=exc.recoverable
                )

            normalized = AIContractNormalizer.normalize_failure(
                exc=wrapped_exc, request=contract_request, response=response
            )

            # Telemetry logging for failures
            logger.error(
                EventID.LOG_ERROR,
                f"AI Contract execution failed: {normalized.error.message if normalized.error else str(exc)}",
                component="AIContract",
                schema=contract_request.response_schema.__name__,
                request_id=response.request_id if response else None,
                correlation_id=response.correlation_id if response else None,
                error_type=(
                    normalized.error.error_type if normalized.error else "unknown"
                ),
                is_retryable=(
                    normalized.error.is_retryable if normalized.error else False
                ),
            )

            return normalized
