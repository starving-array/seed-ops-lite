"""Orchestration gateway coordinating provider execution, validation, cost estimation, and telemetry."""

import time
import uuid

from app.core.context.context import get_context
from app.core.logging.logging import logger
from app.core.settings.config import settings
from app.llm.models import LLMRequest, LLMResponse
from app.llm.provider import GeminiProvider, LLMProvider
from app.llm.retry import execute_with_retry
from app.llm.validation import validate_response_text
from app.prompts.models import RenderedPrompt
from app.telemetry.events import EventID


class LLMGateway:
    """Enterprise gateway responsible for routing and securing all LLM API communications."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Initialize the LLMGateway.

        Args:
            provider: Concrete provider engine (defaults to GeminiProvider).
        """
        self._provider = provider or GeminiProvider()

    async def generate(
        self,
        request: RenderedPrompt | LLMRequest,
        json_mode: bool | None = None,
    ) -> LLMResponse:
        """Generate content from the configured language model.

        Tracks latency, counts tokens, handles retries, performs response checks,
        and logs events.

        Args:
            request: Unified request options or pre-rendered prompt.
            json_mode: Option override to force structured JSON response.

        Returns:
            LLMResponse: Structured response with metadata.

        Raises:
            Exception: Any validation or transient error if retries fail.
        """
        ctx = get_context()
        request_id = str(uuid.uuid4())
        correlation_id = ctx.correlation_id or str(uuid.uuid4())

        if isinstance(request, RenderedPrompt):
            prompt_text = request.prompt_text
            system_instruction = request.system_instruction
            model = request.model or settings.GEMINI_MODEL
            temperature = (
                request.temperature if request.temperature is not None else 0.0
            )
            max_tokens = (
                request.max_output_tokens
                if request.max_output_tokens is not None
                else 2048
            )

            # If json_mode is not explicitly specified, inspect expected_response or prompt
            resolved_json_mode = json_mode
            if resolved_json_mode is None:
                resolved_json_mode = (
                    request.expected_response is not None
                    and "json" in request.expected_response.lower()
                )

            provider_request = LLMRequest(
                prompt=prompt_text,
                system_instruction=system_instruction,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=resolved_json_mode,
            )
            prompt_hash = request.prompt_hash
            template_name = request.template_name
            template_version = request.template_version
            timeout = request.timeout_seconds or settings.LLM_TIMEOUT
            retry_count = request.retry_count or settings.LLM_MAX_RETRIES
            provider_name = request.provider or "Google"
        else:
            provider_request = request
            prompt_text = request.prompt
            system_instruction = request.system_instruction
            model = request.model or settings.GEMINI_MODEL
            resolved_json_mode = (
                json_mode if json_mode is not None else request.json_mode
            )
            prompt_hash = None
            template_name = None
            template_version = None
            timeout = settings.LLM_TIMEOUT
            retry_count = settings.LLM_MAX_RETRIES
            provider_name = "Google"

        start_time = time.perf_counter()

        # Log LLM Request
        logger.info(
            EventID.LLM_REQUEST,
            "LLM API request dispatch initiated",
            component="LLMGateway",
            request_id=request_id,
            correlation_id=correlation_id,
            prompt_hash=prompt_hash,
            template_name=template_name,
            template_version=template_version,
            provider=provider_name,
            model=model,
        )

        try:
            # Wrapped provider invocation to run within the retry handler
            async def call_provider() -> LLMResponse:
                return await self._provider.generate(
                    provider_request,
                    correlation_id=correlation_id,
                    timeout=timeout,
                )

            # Execute provider call with retry backoff wrapper
            response = await execute_with_retry(call_provider, max_retries=retry_count)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Backfill latency and request ID details
            response.usage.latency_ms = round(latency_ms, 2)
            response.request_id = request_id

            # Validate generated text response
            validate_response_text(response.text, resolved_json_mode)

            # Log LLM Response success
            logger.info(
                EventID.LLM_RESPONSE,
                "LLM API request succeeded",
                component="LLMGateway",
                request_id=request_id,
                correlation_id=correlation_id,
                prompt_hash=prompt_hash,
                template_name=template_name,
                template_version=template_version,
                provider=response.usage.provider,
                model=response.usage.model,
                latency_ms=response.usage.latency_ms,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                estimated_cost=response.usage.estimated_cost,
            )

            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            # Log LLM Failure
            logger.error(
                EventID.LLM_ERROR,
                f"LLM API request failed: {exc}",
                component="LLMGateway",
                request_id=request_id,
                correlation_id=correlation_id,
                prompt_hash=prompt_hash,
                template_name=template_name,
                template_version=template_version,
                provider=provider_name,
                model=model,
                latency_ms=round(latency_ms, 2),
                error=str(exc),
            )
            raise exc
