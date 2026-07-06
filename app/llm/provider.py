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
from app.llm.token_accounting import calculate_cost, estimate_tokens
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

        start_time = time.perf_counter()
        target_timeout = timeout if timeout is not None else settings.LLM_TIMEOUT
        try:
            async with httpx.AsyncClient(timeout=target_timeout) as client:
                response = await client.post(url, json=payload)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Gemini API request timed out after {target_timeout} seconds: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Gemini API connection error: {exc}", recoverable=True
            ) from exc

        # Handle rate limits
        if response.status_code == 429:
            raise LLMRateLimitError(
                "Gemini API rate limit exceeded.",
                details={"status_code": 429, "body": response.text},
            )

        # Handle server-side transient errors
        if response.status_code >= 500:
            raise LLMProviderError(
                f"Gemini server error: HTTP {response.status_code}.",
                details={"status_code": response.status_code, "body": response.text},
                status_code=response.status_code,
                recoverable=True,
            )

        # Handle other non-success codes
        if response.status_code != 200:
            raise LLMProviderError(
                f"Gemini API returned HTTP status {response.status_code}: {response.text}",
                details={"status_code": response.status_code, "body": response.text},
                status_code=response.status_code,
                recoverable=False,
            )

        try:
            response_json = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "Failed to parse Gemini response body as JSON.",
                details={"body": response.text},
            ) from exc

        # Check for candidates
        candidates = response_json.get("candidates", [])
        if not candidates:
            # Check for error details inside the JSON
            error_data = response_json.get("error", {})
            error_msg = error_data.get("message", "No response candidates returned.")
            raise LLMProviderError(
                f"Gemini API Error response: {error_msg}", details=response_json
            )

        first_candidate = candidates[0]

        # Verify finish reason
        finish_reason = first_candidate.get("finishReason")
        if finish_reason and finish_reason not in ("STOP", "MAX_TOKENS"):
            raise LLMProviderError(
                f"Gemini completion blocked or failed with reason: {finish_reason}",
                details=first_candidate,
            )

        content = first_candidate.get("content", {})
        parts = content.get("parts", [])
        if not parts:
            raise LLMProviderError(
                "Gemini API returned a response candidate with no text parts.",
                details=first_candidate,
            )

        # Extract output text
        text = parts[0].get("text", "")

        # Extract token usage metadata if available
        usage_metadata = response_json.get("usageMetadata", {})
        prompt_tokens = usage_metadata.get("promptTokenCount", 0)
        completion_tokens = usage_metadata.get("candidatesTokenCount", 0)

        # Fallback estimation if token metrics are missing
        if prompt_tokens == 0:
            prompt_tokens = estimate_tokens(request.prompt)
        if completion_tokens == 0:
            completion_tokens = estimate_tokens(text)

        total_tokens = prompt_tokens + completion_tokens
        estimated_cost = calculate_cost(model, prompt_tokens, completion_tokens)

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
            raw_response=response_json,
            correlation_id=correlation_id,
        )
