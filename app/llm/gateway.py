"""Orchestration gateway coordinating provider execution, validation, cost estimation, and telemetry."""

# ruff: noqa: B023

import contextlib
import inspect
import time
import typing
import uuid
from datetime import UTC
from typing import Any

from app.core.context.context import get_context
from app.core.logging.logging import logger
from app.core.settings.config import settings
from app.llm.config_resolver import resolve_llm_config, validate_llm_config
from app.llm.exceptions import LLMProviderError, LLMValidationError
from app.llm.models import LLMRequest, LLMResponse
from app.llm.provider import LLMProvider, provider_registry
from app.llm.retry import execute_with_retry
from app.llm.telemetry_persistence import persist_llm_telemetry
from app.llm.validation import validate_response_text
from app.prompts.models import RenderedPrompt
from app.telemetry.events import EventID


class LLMGateway:
    """Enterprise gateway responsible for routing and securing all LLM API communications."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Initialize the LLMGateway.

        Args:
            provider: Concrete provider engine (defaults to resolved provider).
        """
        # Kept as self._provider for test mocking backward compatibility
        self._provider = provider

    async def generate(
        self,
        request: RenderedPrompt | LLMRequest,
        json_mode: bool | None = None,
        validator_callback: "typing.Callable[[LLMResponse], None] | None" = None,
    ) -> LLMResponse:
        """Generate content from the configured language model.

        Tracks latency, counts tokens, handles retries, performs response checks,
        and logs events. Supports failover when LLM_AUTO_FAILOVER is enabled.
        """
        # Resolve configuration centrally
        llm_config = resolve_llm_config()
        validate_llm_config(llm_config)

        ctx = get_context()
        request_id = str(uuid.uuid4())
        correlation_id = ctx.correlation_id or str(uuid.uuid4())

        configured_model = llm_config["model"]
        configured_provider = llm_config["provider"]
        configured_timeout = llm_config["timeout"]
        configured_retries = llm_config["max_retries"]
        auto_failover = llm_config.get("auto_failover", True)
        fallback_order = llm_config.get(
            "fallback_order", ["vertex", "gemini", "anthropic", "openai", "ollama"]
        )

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
            provider_name = request.provider or configured_provider

        # Auto-routing: if no specific provider was requested, pick the first
        # available one from the fallback order.  When a model is known to be
        # available only on a subset of providers, prefer those.
        auto_routing = getattr(settings, "LLM_AUTO_ROUTING", True)
        if auto_routing and not provider_name:
            logger.info(
                EventID.LLM_REQUEST,
                "No provider specified — auto-routing to first available provider",
                component="LLMGateway",
            )
            routing_order = _resolve_routing_order(model, fallback_order)
            for candidate in routing_order:
                try:
                    candidate_prov = provider_registry.getProvider(candidate)
                    if candidate_prov.is_available():
                        provider_name = candidate
                        logger.info(
                            EventID.LLM_REQUEST,
                            f"Auto-routing selected: {provider_name}",
                            component="LLMGateway",
                        )
                        break
                    logger.debug(
                        EventID.LOG_INFO,
                        f"Skipping unavailable provider in auto-route: {candidate}",
                    )
                except Exception:  # noqa: S112
                    continue
            if not provider_name:
                provider_name = fallback_order[0]
                logger.warning(
                    EventID.LOG_WARNING,
                    f"No available provider found — falling back to {provider_name}",
                    component="LLMGateway",
                )

        # Setup provider list to try:
        # 1. Custom provider if supplied via gateway constructor
        # 2. Configured / auto-routed provider
        # 3. Fallbacks if failover is enabled
        providers_to_try = []
        if self._provider:
            providers_to_try.append((provider_name, self._provider))
            auto_failover = False
        else:
            try:
                p_inst = provider_registry.getProvider(provider_name)
                providers_to_try.append((provider_name, p_inst))
            except Exception:
                p_inst = provider_registry.getProvider("gemini")
                providers_to_try.append(("gemini", p_inst))

        if auto_failover:
            for fallback in fallback_order:
                if fallback != provider_name:
                    with contextlib.suppress(Exception):
                        p_inst = provider_registry.getProvider(fallback)
                        if p_inst.is_available():
                            providers_to_try.append((fallback, p_inst))
                        else:
                            logger.debug(
                                EventID.LOG_INFO,
                                f"Skipping unavailable fallback provider: {fallback}",
                            )

        last_exception = None
        attempt_number = 0
        failover_count = 0

        for current_prov_name, active_provider in providers_to_try:
            if attempt_number > 0:
                failover_count += 1
                # Adjust model name for fallback provider default if model is not compatible
                if current_prov_name == "openai":
                    provider_request.model = "gpt-4o"
                elif current_prov_name == "anthropic":
                    provider_request.model = "claude-3-5-sonnet"
                elif current_prov_name == "ollama":
                    provider_request.model = "llama3"
                elif current_prov_name == "fireworks":
                    provider_request.model = settings.FIREWORKS_MODEL
                elif current_prov_name == "rocm":
                    provider_request.model = "gemma-2-9b-it"
                elif current_prov_name in ("google", "gemini", "vertex"):
                    provider_request.model = "gemini-2.5-flash"

            from datetime import datetime

            start_time_dt = datetime.now(UTC)
            start_time_iso = start_time_dt.isoformat()
            start_time = time.perf_counter()
            attempt_tracker = {"count": 0}

            logger.info(
                EventID.LLM_REQUEST,
                f"LLM API request dispatch initiated on provider: {current_prov_name}",
                component="LLMGateway",
                request_id=request_id,
                correlation_id=correlation_id,
                prompt_hash=prompt_hash,
                template_name=template_name,
                template_version=template_version,
                provider=current_prov_name,
                model=provider_request.model or model,
            )

            try:

                async def call_provider() -> LLMResponse:
                    attempt_tracker["count"] += 1
                    resp = await active_provider.generate(
                        provider_request,
                        correlation_id=correlation_id,
                        timeout=timeout,
                    )
                    # Check JSON validity inside retry loop
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
                                validate_response_text(resp.text, resolved_json_mode)
                                if validator_callback:
                                    validator_callback(resp)
                                return resp
                            except Exception as repair_exc:
                                repair_details = getattr(
                                    repair_exc, "details", None
                                ) or {"error": str(repair_exc)}
                                raise LLMValidationError(
                                    message=f"Contract validation failed after repair: {repair_exc}",
                                    details=repair_details,
                                ) from repair_exc

                        if not isinstance(eval_exc, LLMValidationError):
                            eval_exc = LLMValidationError(
                                message=f"Contract structural validation failed: {eval_exc}",
                                details=getattr(eval_exc, "details", None)
                                or {"error": str(eval_exc)},
                            )
                        raise eval_exc
                    return resp

                response = await execute_with_retry(
                    call_provider, max_retries=retry_count
                )
                end_time_dt = datetime.now(UTC)
                end_time_iso = end_time_dt.isoformat()
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                response.usage.latency_ms = round(latency_ms, 2)
                response.request_id = request_id
                response_type = getattr(response, "response_type", "text")

                # Cost estimation check
                estimated_cost = getattr(response.usage, "estimated_cost", None)
                if estimated_cost is None:
                    estimated_cost = active_provider.estimateCost(
                        response.usage.model,
                        response.usage.prompt_tokens or 0,
                        response.usage.completion_tokens or 0,
                    )
                if inspect.iscoroutine(estimated_cost) or hasattr(
                    estimated_cost, "_is_coroutine"
                ):
                    estimated_cost = 0.0
                response.usage.estimated_cost = estimated_cost

                # If provider returns no usage metadata: log warning
                if response.usage.prompt_tokens is None:
                    logger.warning(EventID.LOG_WARNING, "Usage metadata unavailable")

                # Store telemetry record
                telemetry_record = {
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "provider": current_prov_name,
                    "model": response.usage.model,
                    "skill_name": template_name or "N/A",
                    "template_name": template_name,
                    "template_version": template_version,
                    "start_time": start_time_iso,
                    "end_time": end_time_iso,
                    "latency_ms": response.usage.latency_ms,
                    "retry_count": attempt_tracker["count"] - 1,
                    "finish_reason": response.finish_reason,
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                    "status": "SUCCESS",
                    "error_message": None,
                    # Backwards compatibility fields:
                    "skill": template_name or "N/A",
                    "response_type": response_type,
                    "attempt_number": attempt_tracker["count"],
                    "max_attempts": retry_count + 1,
                    "failover_count": failover_count,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                    "estimated_cost": estimated_cost,
                    "authentication_method": (
                        "MockAuth"
                        if inspect.iscoroutine(active_provider.auth_status())
                        else active_provider.auth_status()
                    ),
                }
                ctx.llm_telemetry.append(telemetry_record)
                persist_llm_telemetry(telemetry_record)

                def val(v: Any) -> str:
                    if v is None:
                        return "Unavailable"
                    if inspect.iscoroutine(v):
                        return "MockProvider"
                    return str(v)

                log_block = (
                    f"\n==================================================\n"
                    f"LLM REQUEST TELEMETRY\n"
                    f"==================================================\n"
                    f"Provider: {val(active_provider.name())}\n"
                    f"Model: {val(response.usage.model)}\n"
                    f"Skill: {val(template_name or 'N/A')}\n"
                    f"Latency: {val(response.usage.latency_ms)} ms\n"
                    f"Retry Count: {attempt_tracker['count'] - 1}\n"
                    f"Prompt Tokens: {val(response.usage.prompt_tokens)}\n"
                    f"Completion Tokens: {val(response.usage.completion_tokens)}\n"
                    f"Total Tokens: {val(response.usage.total_tokens)}\n"
                    f"Finish Reason: {val(response.finish_reason)}\n"
                    f"Status: SUCCESS\n"
                    f"=================================================="
                )
                logger.info(EventID.LLM_RESPONSE, log_block, component="LLMGateway")
                return response

            except Exception as exc:
                end_time_dt = datetime.now(UTC)
                end_time_iso = end_time_dt.isoformat()
                latency_ms = (time.perf_counter() - start_time) * 1000.0

                prompt_tk = getattr(exc, "prompt_tokens", None)
                completion_tk = getattr(exc, "completion_tokens", None)
                total_tk = getattr(exc, "total_tokens", None)

                if prompt_tk is None:
                    logger.warning(EventID.LOG_WARNING, "Usage metadata unavailable")

                telemetry_record = {
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "provider": current_prov_name,
                    "model": provider_request.model or model,
                    "skill_name": template_name or "N/A",
                    "template_name": template_name,
                    "template_version": template_version,
                    "start_time": start_time_iso,
                    "end_time": end_time_iso,
                    "latency_ms": round(latency_ms, 2),
                    "retry_count": attempt_tracker["count"] - 1,
                    "finish_reason": getattr(exc, "finish_reason", None),
                    "prompt_tokens": prompt_tk,
                    "completion_tokens": completion_tk,
                    "total_tokens": total_tk,
                    "status": "FAILED",
                    "error_message": str(exc),
                    # Backwards compatibility fields:
                    "skill": template_name or "N/A",
                    "response_type": "unknown",
                    "attempt_number": attempt_tracker["count"],
                    "max_attempts": retry_count + 1,
                    "failover_count": failover_count,
                    "usage": {
                        "prompt_tokens": prompt_tk,
                        "completion_tokens": completion_tk,
                        "total_tokens": total_tk,
                    },
                    "estimated_cost": 0.0,
                    "authentication_method": (
                        "MockAuth"
                        if inspect.iscoroutine(active_provider.auth_status())
                        else active_provider.auth_status()
                    ),
                }
                ctx.llm_telemetry.append(telemetry_record)
                persist_llm_telemetry(telemetry_record)

                def val_fail(v: Any) -> str:
                    if v is None:
                        return "Unavailable"
                    return str(v)

                log_block_fail = (
                    f"\n==================================================\n"
                    f"LLM REQUEST FAILURE\n"
                    f"==================================================\n"
                    f"Provider: {current_prov_name}\n"
                    f"Model: {provider_request.model or model}\n"
                    f"Skill: {template_name or 'N/A'}\n"
                    f"Latency: {round(latency_ms, 2)} ms\n"
                    f"Retry Count: {attempt_tracker['count'] - 1}\n"
                    f"Prompt Tokens: {val_fail(prompt_tk)}\n"
                    f"Completion Tokens: {val_fail(completion_tk)}\n"
                    f"Total Tokens: {val_fail(total_tk)}\n"
                    f"Finish Reason: {val_fail(getattr(exc, 'finish_reason', None))}\n"
                    f"Status: FAILED\n"
                    f"Error: {exc!s}\n"
                    f"=================================================="
                )
                logger.error(EventID.LLM_ERROR, log_block_fail, component="LLMGateway")

                last_exception = exc
                attempt_number += attempt_tracker["count"]

                # Log failover attempt fail
                logger.warning(
                    EventID.LOG_WARNING,
                    f"Provider {current_prov_name} failed. Attempting next fallback if available. Error: {exc}",
                    component="LLMGateway",
                )

        # If all providers fail:
        raise last_exception or LLMProviderError(
            "All LLM providers failed to generate content."
        )


# ── Model-aware routing ───────────────────────────────────────────────


def _resolve_routing_order(
    model: str,
    fallback_order: list[str],
) -> list[str]:
    """Return providers in priority order for the given model.

    Certain models are only available on a subset of providers.  When such
    a model is detected the preferred providers are promoted to the front
    of the list so they are tried first.
    """
    model_lower = model.lower()

    # Gemma models: prefer local ROCm, then Fireworks API (hosted Gemma)
    if "gemma" in model_lower:
        preferred = ["rocm", "fireworks"]
        rest = [p for p in fallback_order if p not in preferred]
        return preferred + rest

    return fallback_order
