"""Orchestration gateway coordinating provider execution, validation, cost estimation, and telemetry."""

import time
import typing
import uuid
from typing import Any

from app.core.context.context import get_context
from app.core.logging.logging import logger
from app.llm.config_resolver import resolve_llm_config, validate_llm_config
from app.llm.exceptions import LLMValidationError
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
        validator_callback: "typing.Callable[[LLMResponse], None] | None" = None,
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
        # Resolve configuration centrally
        llm_config = resolve_llm_config()
        validate_llm_config(llm_config)

        ctx = get_context()
        request_id = str(uuid.uuid4())
        correlation_id = ctx.correlation_id or str(uuid.uuid4())

        configured_model = llm_config["model"]
        configured_provider = llm_config["provider"].capitalize()
        configured_timeout = llm_config["timeout"]
        configured_retries = llm_config["max_retries"]

        if isinstance(request, RenderedPrompt):
            prompt_text = request.prompt_text
            system_instruction = request.system_instruction
            model = request.model or configured_model
            temperature = (
                request.temperature
                if request.temperature is not None
                else llm_config["temperature"]
            )
            max_tokens = (
                request.max_output_tokens
                if request.max_output_tokens is not None
                else llm_config["max_output_tokens"]
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
            timeout = request.timeout_seconds or configured_timeout
            retry_count = request.retry_count or configured_retries
            provider_name = request.provider or configured_provider
        else:
            provider_request = request
            prompt_text = request.prompt
            system_instruction = request.system_instruction
            model = request.model or configured_model
            resolved_json_mode = (
                json_mode if json_mode is not None else request.json_mode
            )
            prompt_hash = None
            template_name = None
            template_version = None
            timeout = configured_timeout
            retry_count = configured_retries
            provider_name = configured_provider

        start_time = time.perf_counter()

        attempt_tracker = {"count": 0}

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
                attempt_tracker["count"] += 1
                resp = await self._provider.generate(
                    provider_request,
                    correlation_id=correlation_id,
                    timeout=timeout,
                )
                # Check JSON validity inside retry loop so errors are caught and retried
                try:
                    validate_response_text(resp.text, resolved_json_mode)
                    if validator_callback:
                        validator_callback(resp)
                except Exception as eval_exc:
                    is_last_attempt = attempt_tracker["count"] > retry_count
                    if is_last_attempt and resolved_json_mode:
                        try:
                            from app.llm.validation import repair_json

                            repaired_text = repair_json(resp.text)
                            resp.text = repaired_text
                            # re-validate after repair
                            validate_response_text(resp.text, resolved_json_mode)
                            if validator_callback:
                                validator_callback(resp)
                            return resp
                        except Exception as repair_exc:
                            # If repair also fails, raise LLMValidationError propagating details
                            repair_details = getattr(repair_exc, "details", None) or {
                                "error": str(repair_exc)
                            }
                            raise LLMValidationError(
                                message=f"Contract structural validation failed after JSON repair: {repair_exc}",
                                details=repair_details,
                            ) from repair_exc

                    candidates = (
                        resp.raw_response.get("candidates", [])
                        if resp.raw_response
                        else []
                    )
                    finish_reason = (
                        candidates[0].get("finishReason") if candidates else "UNKNOWN"
                    )
                    logger.warning(
                        EventID.LOG_WARNING,
                        f"LLM validation failed (finish_reason={finish_reason}). "
                        f"Prompt tokens: {resp.usage.prompt_tokens}, "
                        f"Completion tokens: {resp.usage.completion_tokens}. Error: {eval_exc}",
                        component="LLMGateway",
                        finish_reason=finish_reason,
                        prompt_tokens=resp.usage.prompt_tokens,
                        completion_tokens=resp.usage.completion_tokens,
                    )
                    # Convert to LLMValidationError so it's classified correctly
                    if not isinstance(eval_exc, LLMValidationError):
                        eval_exc = LLMValidationError(
                            message=f"Contract structural validation failed: {eval_exc}",
                            details={"error": str(eval_exc)},
                        )
                    raise eval_exc
                return resp

            # Execute provider call with retry backoff wrapper
            response = await execute_with_retry(call_provider, max_retries=retry_count)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Backfill latency and request ID details
            response.usage.latency_ms = round(latency_ms, 2)
            response.request_id = request_id

            response_type = getattr(response, "response_type", "text")

            # Store telemetry record in the execution context list
            telemetry_record = {
                "provider": response.usage.provider,
                "model": response.usage.model,
                "skill": template_name or "N/A",
                "status": "SUCCESS",
                "response_type": response_type,
                "attempt_number": attempt_tracker["count"],
                "max_attempts": retry_count + 1,
                "retry_count": attempt_tracker["count"] - 1,
                "latency_ms": response.usage.latency_ms,
                "finish_reason": response.finish_reason,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }

            ctx.llm_telemetry.append(telemetry_record)

            def val(v: Any) -> str:
                return "Unavailable" if v is None else str(v)

            # Format console log message
            log_block = (
                f"\n==================================================\n"
                f"LLM REQUEST\n"
                f"==================================================\n"
                f"Provider: {val(response.usage.provider)}\n"
                f"Model: {val(response.usage.model)}\n"
                f"Skill: {val(template_name)}\n"
                f"Status: SUCCESS\n"
                f"Attempt: {val(attempt_tracker['count'])}/{val(retry_count + 1)}\n"
                f"Retries: {val(attempt_tracker['count'] - 1)}\n"
                f"Prompt Tokens: {val(response.usage.prompt_tokens)}\n"
                f"Completion Tokens: {val(response.usage.completion_tokens)}\n"
                f"Total Tokens: {val(response.usage.total_tokens)}\n"
                f"Latency: {val(response.usage.latency_ms)} ms\n"
                f"Finish Reason: {val(response.finish_reason)}\n"
                f"Response Type: {val(response_type)}\n"
                f"=================================================="
            )

            # Log LLM Response success
            logger.info(
                EventID.LLM_RESPONSE,
                log_block,
                component="LLMGateway",
                request_id=request_id,
                correlation_id=correlation_id,
                prompt_hash=prompt_hash,
                template_name=template_name,
                template_version=template_version,
                provider=response.usage.provider,
                model=response.usage.model,
                skill=template_name or "N/A",
                status="SUCCESS",
                response_type=response_type,
                attempt_number=attempt_tracker["count"],
                max_attempts=retry_count + 1,
                retry_count=attempt_tracker["count"] - 1,
                latency_ms=response.usage.latency_ms,
                finish_reason=response.finish_reason,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                estimated_cost=response.usage.estimated_cost,
            )

            return response

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Classify exception
            def classify_exception(  # noqa: PLR0911
                e: Exception,
            ) -> tuple[str, str | None, str]:
                from app.llm.exceptions import (
                    LLMProviderError,
                    LLMRateLimitError,
                    LLMTimeoutError,
                    LLMValidationError,
                )

                if isinstance(e, LLMValidationError):
                    return "text", "STOP", "Contract Validation Failure"
                if isinstance(e, LLMRateLimitError):
                    return "rate_limit", None, "Rate Limit"
                if isinstance(e, LLMTimeoutError):
                    return "unknown", None, "Provider Timeout"
                if isinstance(e, LLMProviderError):
                    msg = str(e)
                    resp_type = getattr(e, "response_type", "unknown")
                    # If response_type is unknown but it's a rate limit error, promote it
                    if "rate limit" in msg.lower():
                        resp_type = "rate_limit"
                    fr = getattr(e, "finish_reason", None)
                    if "SAFETY" in msg:
                        return "safety_block", "SAFETY", "Safety Block"
                    if "RECITATION" in msg:
                        return "recitation_block", "RECITATION", "Recitation Block"
                    if "functionCall" in msg:
                        return "function_call", fr, "Function Call Response"
                    if "empty response candidate" in msg:
                        return "empty_candidate", fr, "Empty Candidate"
                    if "no text parts" in msg or "empty parts" in msg:
                        return "empty_parts", fr, "Empty Parts"
                    if "Failed to parse" in msg or "JSON" in msg:
                        return "unknown", fr, "Invalid JSON"
                    return resp_type, fr, "Unknown Provider Error"
                return "unknown", None, "Unknown Provider Error"

            response_type, finish_reason, error_status = classify_exception(exc)

            # Extract tokens from exception if attached
            prompt_tk = getattr(exc, "prompt_tokens", None)
            completion_tk = getattr(exc, "completion_tokens", None)
            total_tk = getattr(exc, "total_tokens", None)

            # Extract provider error metadata
            provider_error_code = getattr(exc, "provider_error_code", None)
            provider_status = getattr(exc, "provider_status", None)
            provider_message = getattr(exc, "provider_message", None)

            # Store telemetry record in the execution context list
            telemetry_record = {
                "provider": provider_name,
                "model": model,
                "skill": template_name or "N/A",
                "status": error_status,
                "response_type": response_type,
                "attempt_number": attempt_tracker["count"],
                "max_attempts": retry_count + 1,
                "retry_count": attempt_tracker["count"] - 1,
                "latency_ms": round(latency_ms, 2),
                "finish_reason": finish_reason,
                "usage": {
                    "prompt_tokens": prompt_tk,
                    "completion_tokens": completion_tk,
                    "total_tokens": total_tk,
                },
                "provider_error_code": provider_error_code,
                "provider_status": provider_status,
                "provider_message": provider_message,
            }

            ctx.llm_telemetry.append(telemetry_record)

            def val(v: Any) -> str:
                return "Unavailable" if v is None else str(v)

            # Format console log message
            log_block = (
                f"\n==================================================\n"
                f"LLM REQUEST\n"
                f"==================================================\n"
                f"Provider: {val(provider_name)}\n"
                f"Model: {val(model)}\n"
                f"Skill: {val(template_name)}\n"
                f"Status: {val(error_status)}\n"
                f"Attempt: {val(attempt_tracker['count'])}/{val(retry_count + 1)}\n"
                f"Retries: {val(attempt_tracker['count'] - 1)}\n"
                f"Prompt Tokens: {val(prompt_tk)}\n"
                f"Completion Tokens: {val(completion_tk)}\n"
                f"Total Tokens: {val(total_tk)}\n"
                f"Latency: {val(round(latency_ms, 2))} ms\n"
                f"Finish Reason: {val(finish_reason)}\n"
                f"Response Type: {val(response_type)}\n"
                f"=================================================="
            )

            # Log LLM Failure
            logger.error(
                EventID.LLM_ERROR,
                log_block,
                component="LLMGateway",
                request_id=request_id,
                correlation_id=correlation_id,
                prompt_hash=prompt_hash,
                template_name=template_name,
                template_version=template_version,
                provider=provider_name,
                model=model,
                skill=template_name or "N/A",
                status=error_status,
                response_type=response_type,
                attempt_number=attempt_tracker["count"],
                max_attempts=retry_count + 1,
                retry_count=attempt_tracker["count"] - 1,
                latency_ms=round(latency_ms, 2),
                finish_reason=finish_reason,
                prompt_tokens=prompt_tk,
                completion_tokens=completion_tk,
                total_tokens=total_tk,
                error=str(exc),
            )
            raise exc
