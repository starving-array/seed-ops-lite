"""Unit tests for the Core Workflow Execution Engine."""

from unittest.mock import patch

import pytest

from app.workflow.domain.models import WorkflowLifecycleStatus
from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
    WorkflowDefinition,
    WorkflowExecutionPlanner,
)
from app.workflow.execution import (
    MockStepExecutor,
    WorkflowExecutionEngine,
)


@pytest.mark.asyncio
async def test_execution_engine_success() -> None:
    """Verify successful execution flow, step sequencing, and outputs propagation."""
    step1 = StepDefinition(
        id="step-1",
        name="Step 1",
        type=DSLStepType.PROMPT,
        input={"echo": "${workflow.input_val}"},
    )
    step2 = StepDefinition(
        id="step-2",
        name="Step 2",
        type=DSLStepType.GENERATION,
        depends_on=["step-1"],
        input={"prop": "${steps.step-1.output.echo_out}"},
    )
    workflow = WorkflowDefinition(
        id="wf-exec-success",
        name="Execution Success Pipeline",
        steps=[step1, step2],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)

    # Setup executors
    exec1 = MockStepExecutor(custom_outputs={"res1": "hello"})
    exec2 = MockStepExecutor(custom_outputs={"res2": "world"})
    registry = {
        DSLStepType.PROMPT: exec1,
        DSLStepType.GENERATION: exec2,
    }

    engine = WorkflowExecutionEngine(plan, workflow, registry)

    # Mock event dispatcher to track calls
    with patch(
        "app.platform.providers.sqlite.DomainEventDispatcher.dispatch"
    ) as mock_dispatch:
        result = await engine.execute(initial_variables={"input_val": "seedops"})

        assert result.status == WorkflowLifecycleStatus.COMPLETED
        assert result.completed_steps == ["step-1", "step-2"]
        assert result.failed_steps == []
        assert result.skipped_steps == []
        assert result.duration > 0.0

        # Verify context and variable mapping propagation
        assert result.context.variables["input_val"] == "seedops"
        assert result.context.step_outputs["step-1"]["echo_out"] == "seedops"
        assert result.context.step_outputs["step-1"]["res1"] == "hello"
        assert result.context.step_outputs["step-2"]["res2"] == "world"

        # Verify event sequence
        mock_dispatch.assert_any_call(
            "WorkflowStarted",
            {"workflow_id": plan.workflow_id, "execution_id": plan.workflow_id},
        )
        mock_dispatch.assert_any_call("StepStarted", {"step_id": "step-1"})
        mock_dispatch.assert_any_call("StepCompleted", {"step_id": "step-1"})
        mock_dispatch.assert_any_call("StepStarted", {"step_id": "step-2"})
        mock_dispatch.assert_any_call("StepCompleted", {"step_id": "step-2"})
        mock_dispatch.assert_any_call(
            "WorkflowCompleted", {"workflow_id": plan.workflow_id}
        )


@pytest.mark.asyncio
async def test_execution_engine_step_failure() -> None:
    """Verify that a step failure aborts execution and skips downstream steps."""
    step1 = StepDefinition(id="step-1", name="Step 1 Failure", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-2",
        name="Step 2 Skip",
        type=DSLStepType.GENERATION,
        depends_on=["step-1"],
    )
    workflow = WorkflowDefinition(
        id="wf-exec-fail",
        name="Execution Fail Pipeline",
        steps=[step1, step2],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)

    # Setup executors
    exec1 = MockStepExecutor(should_fail=True)
    exec2 = MockStepExecutor()
    registry = {
        DSLStepType.PROMPT: exec1,
        DSLStepType.GENERATION: exec2,
    }

    engine = WorkflowExecutionEngine(plan, workflow, registry)

    with patch(
        "app.platform.providers.sqlite.DomainEventDispatcher.dispatch"
    ) as mock_dispatch:
        result = await engine.execute(initial_variables={})

        assert result.status == WorkflowLifecycleStatus.FAILED
        assert result.completed_steps == []
        assert result.failed_steps == ["step-1"]
        assert result.skipped_steps == ["step-2"]
        assert len(result.errors) > 0

        mock_dispatch.assert_any_call(
            "StepFailed", {"step_id": "step-1", "errors": ["Simulated failure"]}
        )
        mock_dispatch.assert_any_call("StepSkipped", {"step_id": "step-2"})
        mock_dispatch.assert_any_call(
            "WorkflowFailed",
            {"workflow_id": plan.workflow_id, "errors": ["Simulated failure"]},
        )
