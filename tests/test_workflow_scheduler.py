"""Unit tests for the Parallel Dependency Scheduler and failure policies."""

import asyncio

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
    WorkflowFailurePolicy,
)


@pytest.mark.asyncio
async def test_scheduler_parallel_concurrency() -> None:
    """Verify that multiple steps within a stage are executed concurrently and respect limits."""
    step1 = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    step2 = StepDefinition(id="step-2", name="Step 2", type=DSLStepType.PROMPT)
    workflow = WorkflowDefinition(
        id="wf-parallel",
        name="Parallel Test",
        steps=[step1, step2],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)

    # Use a mock executor that tracks concurrent execution count
    concurrent_calls = 0
    max_concurrent = 0

    class TrackingExecutor(MockStepExecutor):
        async def execute(self, step, context):
            nonlocal concurrent_calls, max_concurrent
            concurrent_calls += 1
            max_concurrent = max(max_concurrent, concurrent_calls)
            await asyncio.sleep(0.02)
            concurrent_calls -= 1
            return await super().execute(step, context)

    registry = {
        DSLStepType.PROMPT: TrackingExecutor(),
    }

    engine = WorkflowExecutionEngine(plan, workflow, registry)
    result = await engine.execute(initial_variables={})

    assert result.status == WorkflowLifecycleStatus.COMPLETED
    assert result.completed_steps == ["step-1", "step-2"]
    # Check that both steps were active concurrently (since they belong to Stage 1)
    assert max_concurrent == 2


@pytest.mark.asyncio
async def test_scheduler_fail_fast() -> None:
    """Verify that under FAIL_FAST policy, a failure in stage 1 stops stage 2 entirely."""
    step1 = StepDefinition(id="step-1", name="Step 1 Fail", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-2",
        name="Step 2 Skip",
        type=DSLStepType.GENERATION,
        depends_on=["step-1"],
    )
    workflow = WorkflowDefinition(
        id="wf-fail-fast",
        name="Fail Fast Pipeline",
        steps=[step1, step2],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)

    exec1 = MockStepExecutor(should_fail=True)
    exec2 = MockStepExecutor()
    registry = {
        DSLStepType.PROMPT: exec1,
        DSLStepType.GENERATION: exec2,
    }

    engine = WorkflowExecutionEngine(
        plan, workflow, registry, failure_policy=WorkflowFailurePolicy.FAIL_FAST
    )
    result = await engine.execute(initial_variables={})

    assert result.status == WorkflowLifecycleStatus.FAILED
    assert result.completed_steps == []
    assert result.failed_steps == ["step-1"]
    assert result.skipped_steps == ["step-2"]


@pytest.mark.asyncio
async def test_scheduler_continue_policy() -> None:
    """Verify that under CONTINUE policy, independent steps can still execute on failure."""
    step1 = StepDefinition(id="step-1", name="Step 1 Fail", type=DSLStepType.PROMPT)
    # step-2 depends on step-1 (will be skipped)
    step2 = StepDefinition(
        id="step-2",
        name="Step 2 Skip",
        type=DSLStepType.GENERATION,
        depends_on=["step-1"],
    )
    # step-3 has no dependencies (independent, should execute!)
    step3 = StepDefinition(id="step-3", name="Step 3 Run", type=DSLStepType.GENERATION)
    workflow = WorkflowDefinition(
        id="wf-continue",
        name="Continue Pipeline",
        steps=[step1, step2, step3],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)

    exec1 = MockStepExecutor(should_fail=True)
    exec2 = MockStepExecutor()
    registry = {
        DSLStepType.PROMPT: exec1,
        DSLStepType.GENERATION: exec2,
    }

    engine = WorkflowExecutionEngine(
        plan, workflow, registry, failure_policy=WorkflowFailurePolicy.CONTINUE
    )
    result = await engine.execute(initial_variables={})

    # The workflow is considered failed because a step failed, but step-3 ran
    assert result.status == WorkflowLifecycleStatus.FAILED
    assert "step-3" in result.completed_steps
    assert "step-1" in result.failed_steps
    assert "step-2" in result.skipped_steps
