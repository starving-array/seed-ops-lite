"""Language model provider interface and concrete implementations."""

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.settings.config import settings
from app.llm.exceptions import (
    LLMConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.models import LLMRequest, LLMResponse
from app.llm.token_accounting import calculate_cost
from app.telemetry.token_usage import TokenUsage


class LLMProvider(ABC):
    """Abstract interface representing a language model provider client."""

    @abstractmethod
    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Generate a response from the language model.

        Args:
            request: The structured request parameters.
            correlation_id: Propagating correlation identifier.
            timeout: Optional dynamic execution timeout.

        Returns:
            LLMResponse: The standardized response with token usage metrics.
        """
        pass


class GeminiProvider(LLMProvider):
    """Concrete provider class for Google Gemini REST API."""

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Call the Google Gemini API to generate content.

        Args:
            request: Unified request options.
            correlation_id: Correlation ID for tracing.
            timeout: Optional dynamic execution timeout.

        Returns:
            LLMResponse: Structured response with telemetry stats.
        """
        from app.llm.config_resolver import resolve_llm_config

        llm_config = resolve_llm_config()
        model = request.model or llm_config["model"]
        api_key = llm_config["api_key"]

        if not api_key:
            raise LLMConfigurationError("Gemini API key is not configured.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Construct request payload for Gemini API
        contents = [{"parts": [{"text": request.prompt}]}]
        generation_config: dict[str, Any] = {
            "temperature": request.temperature,
            "maxOutputTokens": request.max_tokens,
        }
        if request.json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }

        if request.system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": request.system_instruction}]
            }

        response_type = "unknown"
        finish_reason = None
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None
        estimated_cost = None
        response_json = {}

        def raise_provider_error(
            message: str,
            details: Any = None,
            recoverable: bool = False,
            status_code: int = 500,
        ) -> None:
            raise LLMProviderError(
                message=message,
                details=details,
                status_code=status_code,
                recoverable=recoverable,
                response_type=response_type,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            )

        start_time = time.perf_counter()
        target_timeout = timeout if timeout is not None else settings.LLM_TIMEOUT
        try:
            async with httpx.AsyncClient(timeout=target_timeout) as client:
                response = await client.post(url, json=payload)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
        except httpx.TimeoutException as exc:
            timeout_err = LLMTimeoutError(
                f"Gemini API request timed out after {target_timeout} seconds: {exc}"
            )
            timeout_err.response_type = "unknown"
            timeout_err.finish_reason = None
            timeout_err.prompt_tokens = None
            timeout_err.completion_tokens = None
            timeout_err.total_tokens = None
            raise timeout_err from exc
        except httpx.RequestError as exc:
            conn_err = LLMProviderError(
                f"Gemini API connection error: {exc}", recoverable=True
            )
            conn_err.response_type = "unknown"
            conn_err.finish_reason = None
            conn_err.prompt_tokens = None
            conn_err.completion_tokens = None
            conn_err.total_tokens = None
            raise conn_err from exc

        # Handle rate limits
        if response.status_code == 429:
            try:
                err_json = response.json()
                err_data = err_json.get("error", {})
                code = err_data.get("code", 429)
                status = err_data.get("status", "RESOURCE_EXHAUSTED")
                message = err_data.get("message", "Gemini API rate limit exceeded.")
            except Exception:
                code = 429
                status = "RESOURCE_EXHAUSTED"
                message = "Gemini API rate limit exceeded."

            rate_err = LLMRateLimitError(
                message,
                details={"status_code": 429, "body": response.text},
            )
            rate_err.response_type = "rate_limit"
            rate_err.finish_reason = None
            rate_err.prompt_tokens = None
            rate_err.completion_tokens = None
            rate_err.total_tokens = None
            rate_err.provider_error_code = code
            rate_err.provider_status = status
            rate_err.provider_message = message
            raise rate_err

        # Handle server-side transient errors
        if response.status_code >= 500:
            try:
                err_json = response.json()
                err_data = err_json.get("error", {})
                code = err_data.get("code")
                status = err_data.get("status")
                message = err_data.get("message")
            except Exception:
                code = response.status_code
                status = "SERVER_ERROR"
                message = f"Gemini server error: HTTP {response.status_code}."

            server_err = LLMProviderError(
                message or f"Gemini server error: HTTP {response.status_code}.",
                details={"status_code": response.status_code, "body": response.text},
                status_code=response.status_code,
                recoverable=True,
            )
            server_err.response_type = "unknown"
            server_err.finish_reason = None
            server_err.prompt_tokens = None
            server_err.completion_tokens = None
            server_err.total_tokens = None
            server_err.provider_error_code = code
            server_err.provider_status = status
            server_err.provider_message = message
            raise server_err

        # Handle other non-success codes
        if response.status_code != 200:
            try:
                err_json = response.json()
                err_data = err_json.get("error", {})
                code = err_data.get("code")
                status = err_data.get("status")
                message = err_data.get("message")
            except Exception:
                code = response.status_code
                status = "HTTP_ERROR"
                message = f"Gemini API returned HTTP status {response.status_code}: {response.text}"

            http_err = LLMProviderError(
                message
                or f"Gemini API returned HTTP status {response.status_code}: {response.text}",
                details={"status_code": response.status_code, "body": response.text},
                status_code=response.status_code,
                recoverable=False,
            )
            http_err.response_type = "unknown"
            http_err.finish_reason = None
            http_err.prompt_tokens = None
            http_err.completion_tokens = None
            http_err.total_tokens = None
            http_err.provider_error_code = code
            http_err.provider_status = status
            http_err.provider_message = message
            raise http_err

        try:
            response_json = response.json()
        except ValueError as exc:
            json_err = LLMProviderError(
                "Failed to parse Gemini response body as JSON.",
                details={"body": response.text},
            )
            json_err.response_type = "unknown"
            json_err.finish_reason = None
            json_err.prompt_tokens = None
            json_err.completion_tokens = None
            json_err.total_tokens = None
            raise json_err from exc

        # Extract token usage metadata if available
        usage_metadata = response_json.get("usageMetadata")
        if usage_metadata is not None:
            prompt_tokens = usage_metadata.get("promptTokenCount")
            completion_tokens = usage_metadata.get("candidatesTokenCount")
            total_tokens = usage_metadata.get("totalTokenCount")
            estimated_cost = calculate_cost(
                model, prompt_tokens or 0, completion_tokens or 0
            )
        else:
            from app.core.logging.logging import logger
            from app.telemetry.events import EventID

            logger.info(
                EventID.LOG_INFO,
                "Usage metadata unavailable from Gemini response.",
                component="GeminiProvider",
            )

        # Determine classification according to strict priority order:
        # 1. SAFETY (safety_block)
        # 2. RECITATION (recitation_block)
        # 3. FUNCTION_CALL (function_call)
        # 4. EMPTY_CANDIDATE (empty_candidate)
        # 5. EMPTY_PARTS (empty_parts)
        # 6. TEXT (text)
        # 7. UNKNOWN (unknown)
        candidates = response_json.get("candidates", [])
        first_candidate = candidates[0] if candidates else {}
        finish_reason = first_candidate.get("finishReason")
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])

        if finish_reason == "SAFETY":
            response_type = "safety_block"
            raise_provider_error(
                "Gemini completion blocked due to SAFETY violations.",
                details=first_candidate,
                recoverable=False,
            )
        elif finish_reason == "RECITATION":
            response_type = "recitation_block"
            raise_provider_error(
                "Gemini completion blocked due to RECITATION.",
                details=first_candidate,
                recoverable=False,
            )
        elif parts and any(
            "functionCall" in part or "functionResponse" in part for part in parts
        ):
            response_type = "function_call"
            raise_provider_error(
                "Gemini API returned a functionCall or functionResponse instead of text.",
                details=first_candidate,
            )
        elif not candidates:
            error_data = response_json.get("error", {})
            error_msg = error_data.get("message", "No response candidates returned.")
            response_type = "empty_candidate"
            raise_provider_error(
                f"Gemini API Error response: {error_msg}", details=response_json
            )
        elif not parts:
            response_type = "empty_parts"
            raise_provider_error(
                f"Gemini API returned an empty response candidate (finishReason={finish_reason}).",
                details=first_candidate,
            )
        elif parts and any("text" in part for part in parts):
            response_type = "text"
        else:
            response_type = "unknown"
            if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS"):
                raise_provider_error(
                    f"Gemini completion failed with reason: {finish_reason}",
                    details=first_candidate,
                    recoverable=False,
                )
            else:
                first_part = parts[0] if parts else {}
                part_keys = list(first_part.keys())
                raise_provider_error(
                    f"Gemini API returned unhandled part type: {part_keys}",
                    details=first_candidate,
                )

        first_part = parts[0]
        text = first_part.get("text", "")

        # Create standardized token usage object
        usage = TokenUsage(
            model=model,
            provider="Google",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            latency_ms=round(latency_ms, 2),
        )

        return LLMResponse(
            text=text,
            usage=usage,
            finish_reason=finish_reason,
            raw_response=response_json,
            correlation_id=correlation_id,
            response_type=response_type,
        )
