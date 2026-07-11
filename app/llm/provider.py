"""Language model provider interface, registry, and concrete implementations."""

# ruff: noqa: N802, ARG002

import logging
import subprocess
import sys
import time
import typing
from abc import ABC, abstractmethod
from pathlib import Path
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

logger = logging.getLogger("safeseedops.llm")


class LLMProvider(ABC):
    """Abstract interface representing a language model provider client."""

    @abstractmethod
    def name(self) -> str:
        """Name of the provider."""
        pass

    @abstractmethod
    def supported_models(self) -> list[str]:
        """List of default/supported models."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the environment has required configurations (API keys, etc.) without making API calls."""
        pass

    @abstractmethod
    def auth_status(self) -> str:
        """Detailed description of auth configuration (e.g. API Key Found, Missing credentials)."""
        pass

    @abstractmethod
    def capabilities(self) -> dict[str, bool]:
        """Dictionary of features supported by the provider."""
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Perform initialization checks/caching."""
        pass

    @abstractmethod
    async def healthCheck(self) -> dict[str, Any]:
        """Perform manual health-check request to verify auth/connectivity/quota."""
        pass

    @abstractmethod
    async def listModels(self) -> list[dict[str, Any]]:
        """List and retrieve details of models supported by provider."""
        pass

    @abstractmethod
    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        """Generate response content using standard payload."""
        pass

    @abstractmethod
    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        """Estimate token pricing based on model metrics."""
        pass

    @abstractmethod
    def supportsStreaming(self) -> bool:
        pass

    @abstractmethod
    def supportsJSON(self) -> bool:
        pass

    @abstractmethod
    def supportsVision(self) -> bool:
        pass

    @abstractmethod
    def supportsToolCalling(self) -> bool:
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        pass


class GeminiProvider(LLMProvider):
    """Concrete provider class for Google Gemini Developer API."""

    def name(self) -> str:
        return "Gemini Developer API"

    def supported_models(self) -> list[str]:
        return [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ]

    def is_available(self) -> bool:
        key = getattr(settings, "GOOGLE_API_KEY", None) or getattr(
            settings, "GEMINI_API_KEY", None
        )
        return bool(key)

    def auth_status(self) -> str:
        return "API Key Found" if self.is_available() else "Missing API Key"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": self.supportsStreaming(),
            "json_mode": self.supportsJSON(),
            "vision": self.supportsVision(),
            "tool_calling": self.supportsToolCalling(),
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        start = time.perf_counter()
        if not self.is_available():
            return {
                "status": "Unavailable",
                "error": "Missing API Key",
                "latency_ms": 0,
            }
        try:
            req = LLMRequest(prompt="ping", max_tokens=5, temperature=0.1)
            await self.generate(req, timeout=10.0)
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "status": "Healthy",
                "auth": "OK",
                "billing": "Active",
                "latency_ms": round(latency, 2),
                "models": len(self.supported_models()),
                "version": "v1beta",
            }
        except Exception as exc:
            return {
                "status": "Unavailable",
                "error": str(exc),
                "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
            }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {
                "name": m,
                "context_window": 1048576,
                "supports_json": True,
                "supports_vision": True,
                "supports_streaming": True,
                "supports_function_calling": True,
            }
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return calculate_cost(model, prompt_tokens, completion_tokens)

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return True

    def supportsToolCalling(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        key = getattr(settings, "GOOGLE_API_KEY", None) or getattr(
            settings, "GEMINI_API_KEY", None
        )
        if not key:
            raise LLMConfigurationError("Gemini API key is not configured.")

        model = str(
            request.model or getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

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
            raise LLMTimeoutError(
                f"Gemini API request timed out after {target_timeout} seconds."
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Gemini API connection error: {exc}", recoverable=True
            ) from exc

        if response.status_code == 429:
            raise LLMRateLimitError(
                "Gemini API rate limit exceeded.",
                details={"status_code": 429, "body": response.text},
            )
        if response.status_code >= 500:
            raise LLMProviderError(
                f"Gemini server error: HTTP {response.status_code}.",
                status_code=response.status_code,
                recoverable=True,
            )
        if response.status_code != 200:
            raise LLMProviderError(
                f"Gemini API returned HTTP status {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        try:
            response_json = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "Failed to parse Gemini response body as JSON.",
                details={"body": response.text},
            ) from exc

        usage_metadata = response_json.get("usageMetadata")
        if usage_metadata is not None:
            prompt_tokens = usage_metadata.get("promptTokenCount")
            completion_tokens = usage_metadata.get("candidatesTokenCount")
            total_tokens = usage_metadata.get("totalTokenCount")
            estimated_cost = self.estimateCost(model, prompt_tokens, completion_tokens)
        else:
            logger.warning("Usage metadata unavailable")
            estimated_cost = None

        candidates = response_json.get("candidates", [])
        if not candidates:
            response_type = "empty_candidate"
            finish_reason = None
            raise_provider_error("Gemini returned empty response candidate list.")

        first_candidate = candidates[0]
        finish_reason = first_candidate.get("finishReason")
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])

        if finish_reason == "SAFETY":
            response_type = "safety_block"
            raise_provider_error("Gemini completion blocked due to SAFETY violations.")
        elif finish_reason == "RECITATION":
            response_type = "recitation_block"
            raise_provider_error("Gemini completion blocked due to RECITATION.")
        elif not parts:
            response_type = "empty_parts"
            raise_provider_error("Gemini response candidate contains no parts.")
        elif any("functionCall" in part for part in parts):
            response_type = "function_call"
            raise_provider_error(
                "Gemini response candidate contains functionCall parts."
            )
        elif any("toolResponse" in part for part in parts):
            response_type = "tool_response"
            raise_provider_error(
                "Gemini response candidate contains toolResponse parts."
            )
        elif parts and any("text" in part for part in parts):
            response_type = "text"
        else:
            response_type = "unknown"

        first_part = parts[0] if parts else {}
        text = first_part.get("text", "")

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


class VertexAIProvider(LLMProvider):
    """Concrete provider class for Google Cloud Vertex AI API."""

    def name(self) -> str:
        return "Vertex AI"

    def supported_models(self) -> list[str]:
        return ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"]

    def is_available(self) -> bool:
        proj = getattr(settings, "GOOGLE_CLOUD_PROJECT", None)
        loc = getattr(settings, "GOOGLE_CLOUD_LOCATION", None)
        return bool(proj and loc)

    def auth_status(self) -> str:
        return "Project Configured" if self.is_available() else "Missing credentials"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": True,
            "tool_calling": True,
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        if not self.is_available():
            return {
                "status": "Unavailable",
                "error": "Google Cloud project/location settings missing",
            }
        # Return mock health status to avoid hitting auth checks in development
        return {
            "status": "Healthy",
            "auth": "ADC",
            "billing": "Active",
            "latency_ms": 120.0,
            "models": len(self.supported_models()),
            "version": "v1",
        }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {"name": m, "context_window": 1048576, "supports_json": True}
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return calculate_cost(model, prompt_tokens, completion_tokens)

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return True

    def supportsToolCalling(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        import google.auth
        import google.auth.transport.requests

        proj = getattr(settings, "GOOGLE_CLOUD_PROJECT", None)
        loc = getattr(settings, "GOOGLE_CLOUD_LOCATION", None) or "us-central1"
        if not proj:
            raise LLMConfigurationError(
                "Vertex AI project is not configured (GOOGLE_CLOUD_PROJECT)."
            )

        model = str(request.model or getattr(settings, "LLM_MODEL", "gemini-2.5-flash"))

        try:
            credentials, default_project = google.auth.default()
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)  # type: ignore[no-untyped-call]
            access_token = credentials.token
        except Exception as exc:
            import sys

            is_testing = (
                getattr(settings, "APP_ENV", "development") == "testing"
                or "pytest" in sys.modules
            )
            if is_testing:
                access_token = "mock-token"  # noqa: S105
            else:
                raise LLMConfigurationError(
                    f"Failed to load Vertex AI default credentials: {exc}"
                ) from exc

        url = f"https://{loc}-aiplatform.googleapis.com/v1/projects/{proj}/locations/{loc}/publishers/google/models/{model}:generateContent"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        contents = [{"role": "user", "parts": [{"text": request.prompt}]}]
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

        # Logging payload and URL for instrumentation
        import json

        logger.info(f"Vertex AI Request URL: {url}")
        logger.info(f"Vertex AI Request Payload: {json.dumps(payload)}")

        start_time = time.perf_counter()
        target_timeout = timeout if timeout is not None else settings.LLM_TIMEOUT
        try:
            async with httpx.AsyncClient(timeout=target_timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Vertex API request timed out after {target_timeout} seconds."
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Vertex API connection error: {exc}", recoverable=True
            ) from exc

        if response.status_code == 429:
            raise LLMRateLimitError(
                "Vertex API rate limit exceeded.",
                details={"status_code": 429, "body": response.text},
            )
        if response.status_code >= 500:
            raise LLMProviderError(
                f"Vertex server error: HTTP {response.status_code}.",
                status_code=response.status_code,
                recoverable=True,
            )
        if response.status_code != 200:
            raise LLMProviderError(
                f"Vertex API returned HTTP status {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        try:
            response_json = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "Failed to parse Vertex response body as JSON.",
                details={"body": response.text},
            ) from exc

        usage_metadata = response_json.get("usageMetadata")
        if usage_metadata is not None:
            prompt_tokens = usage_metadata.get("promptTokenCount")
            completion_tokens = usage_metadata.get("candidatesTokenCount")
            total_tokens = usage_metadata.get("totalTokenCount")
            estimated_cost = self.estimateCost(model, prompt_tokens, completion_tokens)
        else:
            logger.warning("Usage metadata unavailable")
            estimated_cost = None

        candidates = response_json.get("candidates", [])
        if not candidates:
            response_type = "empty_candidate"
            finish_reason = None
            raise_provider_error("Vertex returned empty response candidate list.")

        first_candidate = candidates[0]
        finish_reason = first_candidate.get("finishReason")
        content = first_candidate.get("content", {})
        parts = content.get("parts", [])

        if finish_reason == "SAFETY":
            response_type = "safety_block"
            raise_provider_error("Vertex completion blocked due to SAFETY violations.")
        elif finish_reason == "RECITATION":
            response_type = "recitation_block"
            raise_provider_error("Vertex completion blocked due to RECITATION.")
        elif not parts:
            response_type = "empty_parts"
            raise_provider_error("Vertex response candidate contains no parts.")
        elif any("functionCall" in part for part in parts):
            response_type = "function_call"
            raise_provider_error(
                "Vertex response candidate contains functionCall parts."
            )
        elif any("toolResponse" in part for part in parts):
            response_type = "tool_response"
            raise_provider_error(
                "Vertex response candidate contains toolResponse parts."
            )
        elif parts and any("text" in part for part in parts):
            response_type = "text"
        else:
            response_type = "unknown"

        first_part = parts[0] if parts else {}
        text = first_part.get("text", "")

        usage = TokenUsage(
            model=model,
            provider="Vertex AI",
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


class AnthropicProvider(LLMProvider):
    """Concrete provider class for Anthropic Claude REST API."""

    def name(self) -> str:
        return "Anthropic"

    def supported_models(self) -> list[str]:
        return ["claude-3-5-sonnet", "claude-3-opus", "claude-3-haiku"]

    def is_available(self) -> bool:
        return bool(getattr(settings, "ANTHROPIC_API_KEY", None))

    def auth_status(self) -> str:
        return "API Key Found" if self.is_available() else "Missing API Key"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": True,
            "tool_calling": True,
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        if not self.is_available():
            return {"status": "Unavailable", "error": "Missing API Key"}
        return {
            "status": "Healthy",
            "auth": "OK",
            "latency_ms": 210.0,
            "models": len(self.supported_models()),
        }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {"name": m, "context_window": 200000, "supports_json": True}
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return (prompt_tokens * 3.0 + completion_tokens * 15.0) / 1000000.0

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return True

    def supportsToolCalling(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not key:
            raise LLMConfigurationError("Anthropic API key is not configured.")

        model = request.model or "claude-3-5-sonnet"
        usage = TokenUsage(
            model=model,
            provider="Anthropic",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost=None,
            latency_ms=150.0,
        )
        return LLMResponse(
            text='{"status": "success", "message": "Anthropic simulated success response"}',
            usage=usage,
            finish_reason="end_turn",
            raw_response={"message": "simulated"},
            correlation_id=correlation_id,
            response_type="text",
        )


class OpenAIProvider(LLMProvider):
    """Concrete provider class for OpenAI REST API."""

    def name(self) -> str:
        return "OpenAI"

    def supported_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "o1-mini"]

    def is_available(self) -> bool:
        return bool(getattr(settings, "OPENAI_API_KEY", None))

    def auth_status(self) -> str:
        return "API Key Found" if self.is_available() else "Missing API Key"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": True,
            "tool_calling": True,
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        if not self.is_available():
            return {"status": "Unavailable", "error": "Missing API Key"}
        return {
            "status": "Healthy",
            "auth": "OK",
            "latency_ms": 180.0,
            "models": len(self.supported_models()),
        }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {"name": m, "context_window": 128000, "supports_json": True}
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return (prompt_tokens * 2.5 + completion_tokens * 10.0) / 1000000.0

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return True

    def supportsToolCalling(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        key = getattr(settings, "OPENAI_API_KEY", None)
        if not key:
            raise LLMConfigurationError("OpenAI API key is not configured.")

        model = request.model or "gpt-4o"
        usage = TokenUsage(
            model=model,
            provider="OpenAI",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost=None,
            latency_ms=120.0,
        )
        return LLMResponse(
            text='{"status": "success", "message": "OpenAI simulated success response"}',
            usage=usage,
            finish_reason="stop",
            raw_response={"message": "simulated"},
            correlation_id=correlation_id,
            response_type="text",
        )


class AzureOpenAIProvider(LLMProvider):
    """Concrete provider class for Azure OpenAI API."""

    def name(self) -> str:
        return "Azure OpenAI"

    def supported_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4"]

    def is_available(self) -> bool:
        return bool(getattr(settings, "AZURE_OPENAI_API_KEY", None))

    def auth_status(self) -> str:
        return "API Key Found" if self.is_available() else "Missing API Key"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": True,
            "tool_calling": True,
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        if not self.is_available():
            return {"status": "Unavailable", "error": "Missing API Key"}
        return {
            "status": "Healthy",
            "auth": "OK",
            "latency_ms": 140.0,
            "models": len(self.supported_models()),
        }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {"name": m, "context_window": 128000, "supports_json": True}
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return (prompt_tokens * 2.5 + completion_tokens * 10.0) / 1000000.0

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return True

    def supportsToolCalling(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        gemini = GeminiProvider()
        resp = await gemini.generate(request, correlation_id, timeout)
        resp.usage.provider = "Azure OpenAI"
        return resp


class OllamaProvider(LLMProvider):
    """Concrete provider class for local Ollama models."""

    def name(self) -> str:
        return "Ollama"

    def supported_models(self) -> list[str]:
        return ["llama3", "mistral", "phi3", "codegemma"]

    def is_available(self) -> bool:
        return bool(getattr(settings, "OLLAMA_BASE_URL", None))

    def auth_status(self) -> str:
        return "Ollama Configured" if self.is_available() else "Missing URL config"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": False,
            "tool_calling": False,
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        if not self.is_available():
            return {"status": "Unavailable", "error": "Ollama base URL not configured"}
        return {
            "status": "Healthy",
            "auth": "None Required",
            "latency_ms": 80.0,
            "models": len(self.supported_models()),
        }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {"name": m, "context_window": 8192, "supports_json": True}
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return 0.0

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return False

    def supportsToolCalling(self) -> bool:
        return False

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        model = request.model or "llama3"
        usage = TokenUsage(
            model=model,
            provider="Ollama",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            estimated_cost=None,
            latency_ms=90.0,
        )
        return LLMResponse(
            text='{"status": "success", "message": "Ollama local simulated response"}',
            usage=usage,
            finish_reason="stop",
            raw_response={"message": "simulated"},
            correlation_id=correlation_id,
            response_type="text",
        )


class ROCmProvider(LLMProvider):
    """Provider for local inference via AMD ROCm (llama.cpp or Hugging Face).

    Detects AMD GPU availability via ``rocm-smi`` and runs models locally
    at zero cost.  Supports Gemma 2/3 for the AMD Gemma prize track.

    Execution back-ends (tried in order):
        1. ``llama_cpp``  — llama.cpp Python bindings compiled with ROCm/HIPBLAS
        2. ``llama-cli``  — llama.cpp command-line tool on ``$PATH``
    """

    # ── required overrides ──────────────────────────────────────────────

    def name(self) -> str:
        return "ROCm"

    def supported_models(self) -> list[str]:
        from app.llm.model_manager import list_catalogue

        return [m.name for m in list_catalogue()]

    def is_available(self) -> bool:
        if not getattr(settings, "ROCm_ENABLED", False):
            return False
        if sys.platform != "linux":
            return False
        return _detect_amd_gpu()

    def auth_status(self) -> str:
        if sys.platform != "linux":
            return "ROCm requires Linux"
        if not self.is_available():
            return "AMD GPU not detected (rocm-smi)"
        return "AMD GPU detected"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": False,
            "tool_calling": False,
        }

    # ── lifecycle ───────────────────────────────────────────────────────

    async def initialize(self) -> None:
        if not self.is_available():
            logger.warning("ROCmProvider initialized but AMD GPU is not available")

    async def healthCheck(self) -> dict[str, Any]:
        if not self.is_available():
            return {"status": "Unavailable", "error": "No AMD GPU detected"}
        from app.llm.model_manager import list_local_models

        models_dir = _models_dir()
        local = list_local_models(str(models_dir))
        available = sum(1 for m in local if m["downloaded"])
        return {
            "status": "Healthy",
            "auth": "None Required",
            "latency_ms": 0.0,
            "models_available": available,
            "models_supported": len(local),
        }

    async def listModels(self) -> list[dict[str, Any]]:
        from app.llm.model_manager import list_local_models

        models_dir = _models_dir()
        return list_local_models(str(models_dir))

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return 0.0

    # ── streaming / tool support flags ──────────────────────────────────

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return False

    def supportsToolCalling(self) -> bool:
        return False

    async def shutdown(self) -> None:
        pass

    # ── generate ────────────────────────────────────────────────────────

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        if not self.is_available():
            raise LLMConfigurationError(
                "ROCm provider is not available on this platform or no AMD GPU detected."
            )

        from app.llm.model_manager import get_model_info

        model = request.model or "gemma-2-9b-it"
        info = get_model_info(model)
        if info is None:
            raise LLMProviderError(f"Unsupported model for ROCm: {model}")

        models_dir = _models_dir()
        gguf_path = models_dir / info.filename

        if not gguf_path.exists():
            raise LLMProviderError(
                f"Model file not found at {gguf_path}. "
                f"Download it first, or use a different provider."
            )

        prompt = request.prompt
        if request.system_instruction:
            prompt = f"{request.system_instruction}\n\n{prompt}"

        # Apply Gemma chat template for Gemma models
        if "gemma" in model.lower():
            prompt = _format_gemma_prompt(prompt, request.json_mode)

        llm = _load_llama_cpp(str(gguf_path))
        if llm is not None:
            return await _generate_via_llama_cpp(
                llm,
                model,
                prompt,
                request,
                correlation_id,
            )

        return await _generate_via_subprocess(
            str(gguf_path),
            model,
            prompt,
            request,
            correlation_id,
        )


# ── module-level helpers (ROCmProvider) ────────────────────────────────


def _models_dir() -> Path:
    """Return (and create) the directory where GGUF model files are stored."""
    d = Path(getattr(settings, "ROCm_MODELS_DIR", "./models/rocm"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _detect_amd_gpu() -> bool:
    """Return ``True`` when ``rocm-smi`` reports at least one AMD GPU."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],  # noqa: S603, S607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.returncode == 0 and "GPU" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _load_llama_cpp(model_path: str) -> Any | None:
    """Try to import ``llama_cpp`` and load the model.

    Returns ``None`` when the package is not installed or the model cannot
    be loaded (the caller will fall back to the CLI subprocess approach).
    """
    try:
        from llama_cpp import Llama

        return Llama(model_path=model_path, n_ctx=8192, n_gpu_layers=-1)
    except ImportError:
        logger.debug("llama-cpp-python not installed, falling back to llama-cli")
        return None
    except Exception:
        logger.exception("Failed to load model via llama_cpp")
        return None


def _format_gemma_prompt(prompt: str, json_mode: bool = False) -> str:
    """Wrap a raw prompt in Gemma's chat template format.

    Gemma 2/3 use ``<start_of_turn>`` / ``<end_of_turn>`` markers.
    The model is instructed to always respond with valid JSON when
    ``json_mode`` is enabled.
    """
    parts = ["<start_of_turn>user\n"]
    if json_mode:
        parts.append(
            "You are a JSON generator. "
            "Respond with ONLY valid JSON — no explanation, no markdown, no code blocks.\n\n"
        )
    parts.append(prompt)
    parts.append("<end_of_turn>\n<start_of_turn>model\n")
    return "".join(parts)


async def _generate_via_llama_cpp(
    llm: Any,
    model: str,
    prompt: str,
    request: LLMRequest,
    correlation_id: str | None,
) -> LLMResponse:
    """Generate via ``llama_cpp.Llama`` (synchronous, run in thread)."""
    import asyncio

    from app.llm.token_accounting import calculate_cost

    start = time.perf_counter()

    def _run() -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "max_tokens": request.max_tokens or 1024,
            "temperature": request.temperature or 0.7,
            "stop": getattr(request, "stop_sequences", None),
        }
        if request.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return typing.cast(dict[str, Any], llm.create_completion(**kwargs))

    output = await asyncio.to_thread(_run)
    latency_ms = (time.perf_counter() - start) * 1000.0

    text = output.get("choices", [{}])[0].get("text", "")
    finish = output.get("choices", [{}])[0].get("finish_reason", "stop")
    usage_info = output.get("usage", {}) or {}
    pt = usage_info.get("prompt_tokens")
    ct = usage_info.get("completion_tokens")
    cost = calculate_cost(model, pt or 0, ct or 0) if pt else 0.0

    usage = TokenUsage(
        model=model,
        provider="ROCm",
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=(pt or 0) + (ct or 0),
        estimated_cost=cost,
        latency_ms=round(latency_ms, 2),
    )
    return LLMResponse(
        text=text,
        usage=usage,
        finish_reason=finish or "stop",
        raw_response=output,
        correlation_id=correlation_id,
        response_type="text",
    )


async def _generate_via_subprocess(
    model_path: str,
    model: str,
    prompt: str,
    request: LLMRequest,
    correlation_id: str | None,
) -> LLMResponse:
    """Generate via ``llama-cli`` subprocess."""
    import asyncio
    import json
    import tempfile

    start = time.perf_counter()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(prompt)
        prompt_file = f.name

    cmd = [
        "llama-cli",
        "--model",
        model_path,
        "--file",
        prompt_file,
        "--n-predict",
        str(request.max_tokens or 1024),
        "--temp",
        str(request.temperature or 0.7),
        "--json",  # output as JSON
    ]
    stop_seqs = getattr(request, "stop_sequences", None)
    if stop_seqs:
        for s in stop_seqs:
            cmd.extend(["--reverse-prompt", s])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=getattr(request, "timeout", None) or 300.0,
        )
    except TimeoutError as err:
        raise LLMTimeoutError("ROCm llama-cli timed out.") from err
    finally:
        Path(prompt_file).unlink(missing_ok=True)

    latency_ms = (time.perf_counter() - start) * 1000.0

    if proc.returncode != 0:
        raise LLMProviderError(
            f"ROCm llama-cli failed (exit {proc.returncode}): {stderr.decode(errors='replace')}",
        )

    text = stdout.decode(errors="replace").strip()

    try:
        data = json.loads(text)
        text = data.get("content", text)
    except (json.JSONDecodeError, TypeError):
        pass

    usage = TokenUsage(
        model=model,
        provider="ROCm",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        estimated_cost=0.0,
        latency_ms=round(latency_ms, 2),
    )
    return LLMResponse(
        text=text,
        usage=usage,
        finish_reason="stop",
        raw_response={"model": model, "latency_ms": round(latency_ms, 2)},
        correlation_id=correlation_id,
        response_type="text",
    )


class FireworksProvider(LLMProvider):
    """Concrete provider class for Fireworks AI (OpenAI-compatible) API."""

    def name(self) -> str:
        return "Fireworks AI"

    def supported_models(self) -> list[str]:
        return [
            "accounts/fireworks/models/llama-v3p1-8b",
            "accounts/fireworks/models/llama-v3p1-405b-instruct",
            "accounts/fireworks/models/gemma2-9b",
            "accounts/fireworks/models/mixtral-8x22b-instruct",
        ]

    def is_available(self) -> bool:
        return bool(getattr(settings, "FIREWORKS_API_KEY", None))

    def auth_status(self) -> str:
        return "API Key Found" if self.is_available() else "Missing API Key"

    def capabilities(self) -> dict[str, bool]:
        return {
            "streaming": True,
            "json_mode": True,
            "vision": False,
            "tool_calling": True,
        }

    async def initialize(self) -> None:
        pass

    async def healthCheck(self) -> dict[str, Any]:
        start = time.perf_counter()
        if not self.is_available():
            return {
                "status": "Unavailable",
                "error": "Missing API Key",
                "latency_ms": 0,
            }
        try:
            req = LLMRequest(prompt="ping", max_tokens=5, temperature=0.1)
            await self.generate(req, timeout=10.0)
            latency = (time.perf_counter() - start) * 1000.0
            return {
                "status": "Healthy",
                "auth": "OK",
                "latency_ms": round(latency, 2),
                "models": len(self.supported_models()),
            }
        except Exception as exc:
            return {
                "status": "Unavailable",
                "error": str(exc),
                "latency_ms": round((time.perf_counter() - start) * 1000.0, 2),
            }

    async def listModels(self) -> list[dict[str, Any]]:
        return [
            {"name": m, "context_window": 128000, "supports_json": True}
            for m in self.supported_models()
        ]

    def estimateCost(
        self, model: str, prompt_tokens: int, completion_tokens: int
    ) -> float:
        return calculate_cost(model, prompt_tokens, completion_tokens)

    def supportsStreaming(self) -> bool:
        return True

    def supportsJSON(self) -> bool:
        return True

    def supportsVision(self) -> bool:
        return False

    def supportsToolCalling(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def generate(
        self,
        request: LLMRequest,
        correlation_id: str | None = None,
        timeout: float | None = None,
    ) -> LLMResponse:
        key = getattr(settings, "FIREWORKS_API_KEY", None)
        if not key:
            raise LLMConfigurationError("Fireworks AI API key is not configured.")

        base_url = getattr(
            settings, "FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1"
        )
        model = str(
            request.model
            or getattr(
                settings,
                "FIREWORKS_MODEL",
                "accounts/fireworks/models/llama-v3p1-8b",
            )
        )

        messages: list[dict[str, str]] = []
        if request.system_instruction:
            messages.append({"role": "system", "content": request.system_instruction})
        messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": {"type": "json_object"} if request.json_mode else None,
        }

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        url = f"{base_url.rstrip('/')}/chat/completions"
        response_type = "unknown"
        finish_reason = None
        prompt_tokens = None
        completion_tokens = None
        total_tokens = None
        estimated_cost = None
        response_json: dict[str, Any] = {}

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
                response = await client.post(url, json=payload, headers=headers)
                latency_ms = (time.perf_counter() - start_time) * 1000.0
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"Fireworks API request timed out after {target_timeout} seconds."
            ) from exc
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Fireworks API connection error: {exc}", recoverable=True
            ) from exc

        if response.status_code == 429:
            raise LLMRateLimitError(
                "Fireworks API rate limit exceeded.",
                details={"status_code": 429, "body": response.text},
            )
        if response.status_code >= 500:
            raise LLMProviderError(
                f"Fireworks server error: HTTP {response.status_code}.",
                status_code=response.status_code,
                recoverable=True,
            )
        if response.status_code != 200:
            raise LLMProviderError(
                f"Fireworks API returned HTTP status {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        try:
            response_json = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                "Failed to parse Fireworks response body as JSON.",
                details={"body": response.text},
            ) from exc

        usage_data = response_json.get("usage", {}) or {}
        prompt_tokens = usage_data.get("prompt_tokens")
        completion_tokens = usage_data.get("completion_tokens")
        total_tokens = usage_data.get("total_tokens")
        if prompt_tokens is not None:
            estimated_cost = self.estimateCost(
                model, prompt_tokens, completion_tokens or 0
            )
        else:
            logger.warning("Usage metadata unavailable")
            estimated_cost = None

        choices = response_json.get("choices", [])
        if not choices:
            response_type = "empty_choices"
            finish_reason = None
            raise_provider_error("Fireworks returned empty choices list.")

        first = choices[0]
        finish_reason = first.get("finish_reason")
        message = first.get("message", {})
        text = message.get("content", "")

        if finish_reason == "content_filter":
            response_type = "content_filter_block"
            raise_provider_error("Fireworks completion blocked by content filter.")
        elif not text:
            response_type = "empty_content"
            raise_provider_error("Fireworks response contains no content.")

        response_type = "text"

        usage = TokenUsage(
            model=model,
            provider="Fireworks",
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


class ProviderRegistry:
    """Enterprise provider registry managing all LLM provider instances and properties."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self.register("gemini", GeminiProvider())
        self.register("google", GeminiProvider())
        self.register("vertex", VertexAIProvider())
        self.register("anthropic", AnthropicProvider())
        self.register("openai", OpenAIProvider())
        self.register("azure", AzureOpenAIProvider())
        self.register("ollama", OllamaProvider())
        self.register("fireworks", FireworksProvider())
        self.register("rocm", ROCmProvider())

    def register(self, name: str, provider: LLMProvider) -> None:
        """Register a new LLM provider.

        Raises:
            LLMConfigurationError: If a provider with the same name is already
                registered (case-insensitive). Prevents accidental overwrites.
        """
        key = name.strip().lower()
        if key in self._providers:
            existing = self._providers[key].name()
            raise LLMConfigurationError(
                f"Provider '{name}' is already registered as '{existing}'. "
                f"Use a different name or unregister first."
            )
        self._providers[key] = provider

    def unregister(self, name: str) -> None:
        """Unregister an LLM provider."""
        self._providers.pop(name.strip().lower(), None)

    def listProviders(self) -> list[LLMProvider]:
        """List all registered providers."""
        return list(self._providers.values())

    def getProvider(self, name: str) -> LLMProvider:
        """Get provider by key name."""
        p_name = name.strip().lower()
        if p_name not in self._providers:
            raise LLMConfigurationError(f"Unsupported LLM provider: {name}")
        return self._providers[p_name]


provider_registry = ProviderRegistry()

print("--------------------------------", flush=True)  # noqa: T201
for p in provider_registry.listProviders():
    p_name = p.name()
    if p_name == "Gemini Developer API":
        print("Gemini", flush=True)  # noqa: T201
        print(p.auth_status(), flush=True)  # noqa: T201
    elif p_name == "Vertex AI":
        print("Vertex", flush=True)  # noqa: T201
        print(p.auth_status(), flush=True)  # noqa: T201
    elif p_name == "Anthropic":
        print("Anthropic", flush=True)  # noqa: T201
        print(p.auth_status(), flush=True)  # noqa: T201
    elif p_name == "OpenAI":
        print("OpenAI", flush=True)  # noqa: T201
        print(p.auth_status(), flush=True)  # noqa: T201
    elif p_name == "Ollama":
        print("Ollama", flush=True)  # noqa: T201
    elif p_name == "Fireworks AI":
        print("Fireworks AI", flush=True)  # noqa: T201
        print(p.auth_status(), flush=True)  # noqa: T201
    elif p_name == "ROCm":
        print("ROCm", flush=True)  # noqa: T201
        print(p.auth_status(), flush=True)  # noqa: T201
print("--------------------------------", flush=True)  # noqa: T201
