"""Unit tests for the AI Step Executors and Provider Abstraction."""

import pytest

from app.workflow.ai_execution import (
    ConditionExecutor,
    DelayExecutor,
    GenerationExecutor,
    MockLLMProvider,
    PromptExecutor,
    PromptRenderer,
    TransformExecutor,
    ValidationExecutor,
)
from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
)
from app.workflow.execution import (
    WorkflowExecutionContext,
    WorkflowStepStatus,
)


def test_prompt_renderer_interpolation() -> None:
    """Verify prompt renderer resolves variable and date expressions correctly."""
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
        variables={"customer": "Alice"},
        step_outputs={"step-A": {"text": "hello"}},
    )

    rendered = PromptRenderer.render(
        "Hi ${workflow.customer}, system id ${execution.id}", context
    )
    assert rendered == "Hi Alice, system id exec-456"

    rendered_date = PromptRenderer.render("Date: ${date.now}", context)
    assert "Date: " in rendered_date
    assert rendered_date.endswith("Z")

    rendered_outs = PromptRenderer.render(
        "Result: ${steps.step-A.output.text}", context
    )
    assert rendered_outs == "Result: hello"


def test_prompt_renderer_invalid_reference() -> None:
    """Verify renderer raises ValueError for missing references."""
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
    )

    with pytest.raises(ValueError, match="Unresolved workflow variable: missing_val"):
        PromptRenderer.render("Hi ${workflow.missing_val}", context)

    with pytest.raises(ValueError, match="Unresolved step output path"):
        PromptRenderer.render("Result: ${steps.missing_step.output.text}", context)


@pytest.mark.asyncio
async def test_prompt_executor_success() -> None:
    """Verify prompt step executes and returns output through mock provider."""
    step = StepDefinition(
        id="prompt-step",
        name="Generate prompt",
        type=DSLStepType.PROMPT,
        input={"prompt": "Hi ${workflow.user}"},
    )
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
        variables={"user": "Bob"},
    )

    provider = MockLLMProvider(return_text="Mock Output")
    executor = PromptExecutor(provider)

    result = await executor.execute(step, context)
    assert result.status == WorkflowStepStatus.COMPLETED
    assert result.outputs["text"] == "Mock Output"
    assert result.duration > 0.0


@pytest.mark.asyncio
async def test_generation_executor_json_parsing() -> None:
    """Verify generation executor parses JSON response successfully."""
    step = StepDefinition(
        id="gen-step",
        name="Generate config",
        type=DSLStepType.GENERATION,
        input={"prompt": "Provide config JSON"},
    )
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
    )

    provider = MockLLMProvider(return_text='{"status_code": 200, "message": "OK"}')
    executor = GenerationExecutor(provider)

    result = await executor.execute(step, context)
    assert result.status == WorkflowStepStatus.COMPLETED
    assert result.outputs["structured_output"] == {"status_code": 200, "message": "OK"}
    assert "warnings" not in result.metadata or len(result.warnings) == 0


@pytest.mark.asyncio
async def test_validation_executor_success() -> None:
    """Verify validation step evaluates provider keywords for success tags."""
    step = StepDefinition(
        id="val-step",
        name="Validate input",
        type=DSLStepType.VALIDATION,
        input={"prompt": "Check input", "rules": {"min_len": 5}},
    )
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
    )

    provider1 = MockLLMProvider(return_text="Status is completely successful.")
    executor1 = ValidationExecutor(provider1)
    res1 = await executor1.execute(step, context)
    assert res1.outputs["valid"] is True

    provider2 = MockLLMProvider(return_text="Check failed due to rate limits.")
    executor2 = ValidationExecutor(provider2)
    res2 = await executor2.execute(step, context)
    assert res2.outputs["valid"] is False


@pytest.mark.asyncio
async def test_transform_executor_uppercase() -> None:
    """Verify transform step converts string values to uppercase."""
    step = StepDefinition(
        id="transform-step",
        name="Uppercase payload",
        type=DSLStepType.TRANSFORM,
        input={"message": "hello world", "code": 101},
    )
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
    )

    executor = TransformExecutor()
    result = await executor.execute(step, context)
    assert result.status == WorkflowStepStatus.COMPLETED
    assert result.outputs["message"] == "HELLO WORLD"
    assert result.outputs["code"] == 101


@pytest.mark.asyncio
async def test_delay_executor() -> None:
    """Verify delay executor executes without errors."""
    step = StepDefinition(
        id="delay-step",
        name="Short wait",
        type=DSLStepType.DELAY,
        input={"duration": 0.01},
    )
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
    )

    executor = DelayExecutor()
    result = await executor.execute(step, context)
    assert result.status == WorkflowStepStatus.COMPLETED
    assert result.outputs["delayed_seconds"] == 0.01


@pytest.mark.asyncio
async def test_condition_executor() -> None:
    """Verify condition step evaluates comparisons."""
    step = StepDefinition(
        id="cond-step",
        name="Check matching values",
        type=DSLStepType.CONDITION,
        input={"left": "apple", "right": "apple", "operator": "=="},
    )
    context = WorkflowExecutionContext(
        workflow_id="wf-123",
        execution_id="exec-456",
    )

    executor = ConditionExecutor()
    result = await executor.execute(step, context)
    assert result.status == WorkflowStepStatus.COMPLETED
    assert result.outputs["condition_met"] is True
