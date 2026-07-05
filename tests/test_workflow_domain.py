"""Unit tests for the Workflow Engine Domain Models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.workflow.domain import (
    StepType,
    Workflow,
    WorkflowContext,
    WorkflowExecution,
    WorkflowExecutionState,
    WorkflowLifecycleStatus,
    WorkflowResult,
    WorkflowStep,
    WorkflowVariable,
)


def test_workflow_lifecycle_status_enum() -> None:
    """Verify all required lifecycle statuses are supported."""
    assert WorkflowLifecycleStatus.DRAFT.value == "Draft"
    assert WorkflowLifecycleStatus.READY.value == "Ready"
    assert WorkflowLifecycleStatus.RUNNING.value == "Running"
    assert WorkflowLifecycleStatus.COMPLETED.value == "Completed"
    assert WorkflowLifecycleStatus.FAILED.value == "Failed"
    assert WorkflowLifecycleStatus.CANCELLED.value == "Cancelled"


def test_step_type_enum() -> None:
    """Verify all required workflow step types are supported."""
    assert StepType.PROMPT.value == "Prompt"
    assert StepType.VALIDATION.value == "Validation"
    assert StepType.GENERATION.value == "Generation"
    assert StepType.TRANSFORM.value == "Transform"
    assert StepType.CONDITION.value == "Condition"
    assert StepType.LOOP.value == "Loop"
    assert StepType.MERGE.value == "Merge"
    assert StepType.EXPORT.value == "Export"
    assert StepType.HUMAN_APPROVAL.value == "HumanApproval"


def test_workflow_variable_model() -> None:
    """Verify WorkflowVariable validation and immutability."""
    var = WorkflowVariable(name="max_retries", value=3, description="Retry threshold")
    assert var.name == "max_retries"
    assert var.value == 3
    assert var.description == "Retry threshold"

    # Test Immutability
    with pytest.raises(ValidationError):
        var.name = "new_name"  # type: ignore[misc]


def test_workflow_context_model() -> None:
    """Verify WorkflowContext initializes dictionary mapping."""
    var1 = WorkflowVariable(name="db_host", value="localhost")
    context = WorkflowContext(variables={"db_host": var1})
    assert context.variables["db_host"].value == "localhost"

    # Test Immutability
    with pytest.raises(ValidationError):
        context.variables = {}  # type: ignore[misc]


def test_workflow_step_model_defaults_and_validation() -> None:
    """Verify WorkflowStep default values and structured constraints."""
    step = WorkflowStep(
        id="step-1",
        name="Generate SQL Schema",
        type=StepType.GENERATION,
    )
    assert step.id == "step-1"
    assert step.type == StepType.GENERATION
    assert step.enabled is True
    assert step.retry_count == 0
    assert step.dependencies == []
    assert step.timeout is None

    # Test validation failure with invalid step type
    with pytest.raises(ValidationError):
        WorkflowStep(
            id="step-1",
            name="Invalid Step",
            type="INVALID_TYPE",  # type: ignore[arg-type]
        )


def test_workflow_model() -> None:
    """Verify Workflow parent object composition."""
    step = WorkflowStep(
        id="step-1",
        name="Validation Step",
        type=StepType.VALIDATION,
    )
    wf = Workflow(
        id="wf-100",
        name="SQL Generator Pipeline",
        steps=[step],
        status=WorkflowLifecycleStatus.READY,
    )
    assert wf.id == "wf-100"
    assert len(wf.steps) == 1
    assert wf.steps[0].id == "step-1"
    assert wf.status == WorkflowLifecycleStatus.READY


def test_workflow_execution_state_tracking() -> None:
    """Verify execution state tracks times, states, and counts."""
    start_time = datetime.now(UTC)
    end_time = datetime.now(UTC)
    state = WorkflowExecutionState(
        started_at=start_time,
        finished_at=end_time,
        duration=1.52,
        status=WorkflowLifecycleStatus.RUNNING,
        current_step="step-2",
        completed_steps=["step-1"],
        failed_step=None,
        retry_count=1,
    )
    assert state.status == WorkflowLifecycleStatus.RUNNING
    assert state.started_at == start_time
    assert state.finished_at == end_time
    assert state.duration == 1.52
    assert state.current_step == "step-2"
    assert state.completed_steps == ["step-1"]
    assert state.failed_step is None
    assert state.retry_count == 1


def test_workflow_execution_composition() -> None:
    """Verify top-level WorkflowExecution structure."""
    state = WorkflowExecutionState(status=WorkflowLifecycleStatus.RUNNING)
    context = WorkflowContext()
    exec_run = WorkflowExecution(
        id="exec-42",
        workflow_id="wf-100",
        state=state,
        context=context,
    )
    assert exec_run.id == "exec-42"
    assert exec_run.workflow_id == "wf-100"
    assert exec_run.state.status == WorkflowLifecycleStatus.RUNNING


def test_workflow_result() -> None:
    """Verify final WorkflowResult structures."""
    res = WorkflowResult(
        execution_id="exec-42",
        status=WorkflowLifecycleStatus.COMPLETED,
        output={"export_url": "s3://output"},
        errors=[],
    )
    assert res.execution_id == "exec-42"
    assert res.status == WorkflowLifecycleStatus.COMPLETED
    assert res.output["export_url"] == "s3://output"
    assert len(res.errors) == 0
