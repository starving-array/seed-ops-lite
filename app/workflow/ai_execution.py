"""AI Step Executors, Provider Abstraction, and Prompt Template Rendering."""

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from datetime import UTC
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging.logging import logger
from app.core.settings.config import settings
from app.llm.models import LLMRequest
from app.llm.provider import GeminiProvider
from app.telemetry.events import EventID
from app.workflow.dsl.models import StepDefinition
from app.workflow.execution import (
    WorkflowExecutionContext,
    WorkflowStepExecutor,
    WorkflowStepResult,
    WorkflowStepStatus,
    resolve_value,
)


class ExecutionRequest(BaseModel):
    """The structured parameters passed to an LLM provider."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="Unique workflow identifier.")
    execution_id: str = Field(..., description="Unique execution instance ID.")
    step_id: str = Field(..., description="The step ID triggering the request.")
    prompt: str = Field(..., description="The rendered prompt text.")
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Variables context."
    )
    temperature: float = Field(default=0.7, description="Model sampling temperature.")
    max_tokens: int = Field(default=1024, description="Max response tokens.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom tracking metadata."
    )
    timeout: float | None = Field(
        default=None, description="Request timeout limit in seconds."
    )


class ExecutionMetadata(BaseModel):
    """Execution telemetry and token metrics."""

    model_config = ConfigDict(frozen=True)

    duration: float = Field(..., description="Latency duration of the call in seconds.")
    token_usage: dict[str, int | None] = Field(
        default_factory=dict, description="Usage counts (prompt/completion/total)."
    )
    provider: str = Field(..., description="The name of the LLM provider.")
    model: str = Field(..., description="The target LLM model name used.")
    cost: float | None = Field(
        default=None, description="Calculated usage cost in USD."
    )


class ExecutionResponse(BaseModel):
    """Standardized response return payload from an LLM provider."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(
        ..., description="Response status (success, failed, timeout, etc.)."
    )
    text: str = Field(default="", description="Generated raw response text.")
    structured_output: dict[str, Any] | None = Field(
        default=None, description="Parsed JSON outputs if applicable."
    )
    metadata: ExecutionMetadata = Field(..., description="Call metadata and metrics.")
    warnings: list[str] = Field(default_factory=list, description="Warnings generated.")
    errors: list[str] = Field(
        default_factory=list, description="Error messages captured."
    )


class WorkflowLLMProvider(ABC):
    """Interface representing a generic workflow language model provider client."""

    @abstractmethod
    async def generate(self, request: ExecutionRequest) -> ExecutionResponse:
        """Call the provider endpoint asynchronously."""
        pass


class PromptRenderer:
    """Renders prompt templates containing `${scope.entity}` reference syntax."""

    # Matches any ${expression} format
    EXPRESSION_PATTERN = re.compile(r"\$\{([^\}]+)\}")

    @staticmethod
    def render(template: str, context: WorkflowExecutionContext) -> str:
        """Interpolates dynamic template variables with live context data.

        Args:
            template: The raw template text.
            context: The execution context carrying live variables.

        Returns:
            The fully rendered string.

        Raises:
            ValueError: If there are unresolved references.
        """
        errors = []

        def replacer(match: re.Match[str]) -> str:
            expression = match.group(1).strip()
            res: str = match.group(0)

            if expression == "date.now":
                from datetime import datetime

                res = datetime.now(UTC).isoformat() + "Z"
            elif expression == "execution.id":
                res = context.execution_id
            elif expression.startswith("workflow."):
                var_name = expression[len("workflow.") :]
                if var_name in context.variables:
                    res = str(context.variables[var_name])
                else:
                    errors.append(f"Unresolved workflow variable: {var_name}")
            elif expression.startswith("steps."):
                parts = expression.split(".")
                if len(parts) >= 3 and parts[2] == "output":
                    step_id = parts[1]
                    path = parts[3:]
                    step_outs = context.step_outputs.get(step_id, {})
                    current: Any = step_outs
                    for p in path:
                        if isinstance(current, dict):
                            current = current.get(p)
                        else:
                            current = None
                            break
                    if current is not None:
                        res = str(current)
                    else:
                        errors.append(f"Unresolved step output path: {expression}")
            else:
                errors.append(f"Invalid or unresolved reference: {expression}")

            return res

        rendered = PromptRenderer.EXPRESSION_PATTERN.sub(replacer, template)
        if errors:
            raise ValueError("; ".join(errors))

        return rendered


class WorkflowGeminiProvider(WorkflowLLMProvider):
    """Workflow provider wrapping the existing Google Gemini API provider integration."""

    def __init__(self, gemini_provider: GeminiProvider | None = None) -> None:
        self._provider = gemini_provider or GeminiProvider()

    async def generate(self, request: ExecutionRequest) -> ExecutionResponse:
        start_time = time.perf_counter()

        # Log: Provider Invoked
        logger.info(
            EventID.LOG_INFO,
            "Provider Invoked",
            details={
                "provider": "Gemini",
                "model": settings.GEMINI_MODEL,
                "step_id": request.step_id,
            },
        )

        llm_req = LLMRequest(
            prompt=request.prompt,
            model=settings.GEMINI_MODEL,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        try:
            res = await self._provider.generate(
                llm_req, correlation_id=request.execution_id, timeout=request.timeout
            )
            duration = time.perf_counter() - start_time

            usage = {
                "prompt_tokens": res.usage.prompt_tokens,
                "completion_tokens": res.usage.completion_tokens,
                "total_tokens": res.usage.total_tokens,
            }

            metadata = ExecutionMetadata(
                duration=duration,
                token_usage=usage,
                provider="Gemini",
                model=res.usage.model,
                cost=res.usage.estimated_cost,
            )

            return ExecutionResponse(
                status="success",
                text=res.text,
                metadata=metadata,
            )
        except Exception as e:
            duration = time.perf_counter() - start_time
            metadata = ExecutionMetadata(
                duration=duration,
                provider="Gemini",
                model=settings.GEMINI_MODEL,
            )
            return ExecutionResponse(
                status="failed",
                metadata=metadata,
                errors=[str(e)],
            )


class MockLLMProvider(WorkflowLLMProvider):
    """Simulated provider for testing without issuing live HTTP calls."""

    def __init__(
        self, return_text: str = "Mocked Response text", should_fail: bool = False
    ) -> None:
        self.return_text = return_text
        self.should_fail = should_fail
        self.calls_count = 0

    async def generate(self, _request: ExecutionRequest) -> ExecutionResponse:
        self.calls_count += 1
        duration = 0.05
        metadata = ExecutionMetadata(
            duration=duration,
            token_usage={
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
            provider="Mock",
            model="mock-gpt",
        )

        if self.should_fail:
            return ExecutionResponse(
                status="failed",
                metadata=metadata,
                errors=["Mock provider connection failure"],
            )

        return ExecutionResponse(
            status="success",
            text=self.return_text,
            metadata=metadata,
        )


class BaseWorkflowStepExecutor(WorkflowStepExecutor):
    """Base helper implementation containing validation defaults."""

    def can_execute(
        self, step: StepDefinition, _context: WorkflowExecutionContext
    ) -> bool:
        return step.enabled

    def validate_inputs(
        self, _step: StepDefinition, _context: WorkflowExecutionContext
    ) -> list[str]:
        return []

    def validate_outputs(
        self, _step: StepDefinition, _result: WorkflowStepResult
    ) -> list[str]:
        return []

    def cleanup(self, _step: StepDefinition) -> None:
        pass


class PromptExecutor(BaseWorkflowStepExecutor):
    """Evaluates prompt templates and forwards requests to the LLM Provider."""

    def __init__(self, provider: WorkflowLLMProvider) -> None:
        self.provider = provider

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()

        prompt_tmpl = step.input.get("prompt", "")

        try:
            # Log: Prompt Rendered
            rendered_prompt = PromptRenderer.render(prompt_tmpl, context)
            logger.info(
                EventID.LOG_INFO, "Prompt Rendered", details={"step_id": step.id}
            )
        except ValueError as e:
            return WorkflowStepResult(
                status=WorkflowStepStatus.FAILED,
                duration=time.perf_counter() - start_time,
                errors=[str(e)],
            )

        req = ExecutionRequest(
            workflow_id=context.workflow_id,
            execution_id=context.execution_id,
            step_id=step.id,
            prompt=rendered_prompt,
            temperature=step.input.get("temperature", 0.7),
            timeout=float(step.timeout) if step.timeout else None,
        )

        res = await self.provider.generate(req)
        duration = time.perf_counter() - start_time

        if res.status == "success":
            return WorkflowStepResult(
                status=WorkflowStepStatus.COMPLETED,
                outputs={"text": res.text},
                duration=duration,
            )

        return WorkflowStepResult(
            status=WorkflowStepStatus.FAILED,
            duration=duration,
            errors=res.errors,
        )


class GenerationExecutor(BaseWorkflowStepExecutor):
    """Executes generative instructions and parses output format into structured JSON payload."""

    def __init__(self, provider: WorkflowLLMProvider) -> None:
        self.provider = provider

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()
        prompt_tmpl = step.input.get("prompt", "")

        try:
            rendered_prompt = PromptRenderer.render(prompt_tmpl, context)
        except ValueError as e:
            return WorkflowStepResult(
                status=WorkflowStepStatus.FAILED,
                duration=time.perf_counter() - start_time,
                errors=[str(e)],
            )

        req = ExecutionRequest(
            workflow_id=context.workflow_id,
            execution_id=context.execution_id,
            step_id=step.id,
            prompt=rendered_prompt,
            temperature=step.input.get("temperature", 0.2),
            timeout=float(step.timeout) if step.timeout else None,
        )

        res = await self.provider.generate(req)
        duration = time.perf_counter() - start_time

        if res.status == "success":
            try:
                # Attempt to parse json structure output
                data = json.loads(res.text)
                return WorkflowStepResult(
                    status=WorkflowStepStatus.COMPLETED,
                    outputs={"structured_output": data, "text": res.text},
                    duration=duration,
                )
            except json.JSONDecodeError:
                # Return plain text if not valid json
                return WorkflowStepResult(
                    status=WorkflowStepStatus.COMPLETED,
                    outputs={"text": res.text, "structured_output": {}},
                    duration=duration,
                    warnings=["Generated response was not valid JSON."],
                )

        return WorkflowStepResult(
            status=WorkflowStepStatus.FAILED,
            duration=duration,
            errors=res.errors,
        )


class ValidationExecutor(BaseWorkflowStepExecutor):
    """Validates parameters criteria, returning checks success/failed tags."""

    def __init__(self, provider: WorkflowLLMProvider) -> None:
        self.provider = provider

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()

        # Verify if validation prompt or rules match
        rules = resolve_value(step.input.get("rules", {}), context)
        prompt_tmpl = step.input.get("prompt", "")

        try:
            rendered_prompt = PromptRenderer.render(prompt_tmpl, context)
        except ValueError as e:
            return WorkflowStepResult(
                status=WorkflowStepStatus.FAILED,
                duration=time.perf_counter() - start_time,
                errors=[str(e)],
            )

        req = ExecutionRequest(
            workflow_id=context.workflow_id,
            execution_id=context.execution_id,
            step_id=step.id,
            prompt=f"Rules: {rules}\nPrompt: {rendered_prompt}",
            timeout=float(step.timeout) if step.timeout else None,
        )

        res = await self.provider.generate(req)
        duration = time.perf_counter() - start_time

        if res.status == "success":
            # Simple keyword parsing fallback for mockup validation rules
            valid = "invalid" not in res.text.lower() and "fail" not in res.text.lower()
            return WorkflowStepResult(
                status=WorkflowStepStatus.COMPLETED,
                outputs={"valid": valid, "reason": res.text},
                duration=duration,
            )

        return WorkflowStepResult(
            status=WorkflowStepStatus.FAILED,
            duration=duration,
            errors=res.errors,
        )


class TransformExecutor(BaseWorkflowStepExecutor):
    """Performs light manipulation and mapping transformations over input parameters."""

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()

        # Resolve all inputs mapping first
        inputs = resolve_value(step.input, context)

        # Perform uppercase transformations mapping if target exists
        outputs = {}
        for k, v in inputs.items():
            if isinstance(v, str):
                outputs[k] = v.upper()
            else:
                outputs[k] = v

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs=outputs,
            duration=duration,
        )


class ExportExecutor(BaseWorkflowStepExecutor):
    """Simulated file exporter step."""

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()
        inputs = resolve_value(step.input, context)

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={
                "export_status": "success",
                "file_path": "exported_schemas.sql",
                "records_exported": len(inputs),
            },
            duration=duration,
        )


class HumanApprovalExecutor(BaseWorkflowStepExecutor):
    """Placeholder human approval gating executor."""

    async def execute(
        self, _step: StepDefinition, _context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={"approved": True, "comments": "Auto-approved placeholder"},
            duration=duration,
        )


class DelayExecutor(BaseWorkflowStepExecutor):
    """Suspends the execution flow for a configured period of seconds."""

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()
        duration_sec = resolve_value(step.input.get("duration", 0), context)

        if duration_sec > 0:
            await asyncio.sleep(float(duration_sec))

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={"delayed_seconds": duration_sec},
            duration=duration,
        )


class ConditionExecutor(BaseWorkflowStepExecutor):
    """Evaluates logic matches and triggers branching paths."""

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()
        val1 = resolve_value(step.input.get("left"), context)
        val2 = resolve_value(step.input.get("right"), context)
        op = step.input.get("operator", "==")

        met = False
        if op == "==":
            met = val1 == val2
        elif op == "!=":
            met = val1 != val2

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={"condition_met": met},
            duration=duration,
        )


class LoopExecutor(BaseWorkflowStepExecutor):
    """Placeholder looping controller."""

    async def execute(
        self, _step: StepDefinition, _context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={"loop_completed": True, "iterations": 1},
            duration=duration,
        )


class MergeExecutor(BaseWorkflowStepExecutor):
    """Merges disparate inputs sources maps together."""

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()
        inputs = resolve_value(step.input, context)

        merged_dict = {}
        for val in inputs.values():
            if isinstance(val, dict):
                merged_dict.update(val)

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={"merged": merged_dict},
            duration=duration,
        )


class WebhookExecutor(BaseWorkflowStepExecutor):
    """Trigger dispatch webhooks call simulation."""

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start_time = time.perf_counter()
        url = resolve_value(step.input.get("url", ""), context)

        duration = time.perf_counter() - start_time
        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs={
                "webhook_status": "dispatched",
                "target_url": url,
                "status_code": 200,
            },
            duration=duration,
        )
