"""Unit tests for the Workflow Engine validating state, scheduling, progress, and retries."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.guardian.execution_plan import (
    ExecutionCostEstimate,
    ExecutionPlan,
    PlanningStatistics,
)
from app.workflow import (
    InvalidStateTransitionError,
    RetryPolicy,
    WorkflowEngine,
    WorkflowProgressTracker,
    WorkflowScheduler,
    WorkflowState,
    WorkflowStateMachine,
)


def test_state_machine_transitions() -> None:
    """Verify that WorkflowStateMachine enforces valid transitions and rejects invalid paths."""
    # Valid transitions
    assert (
        WorkflowStateMachine.transition(WorkflowState.PENDING, WorkflowState.VALIDATED)
        == WorkflowState.VALIDATED
    )
    assert (
        WorkflowStateMachine.transition(WorkflowState.VALIDATED, WorkflowState.QUEUED)
        == WorkflowState.QUEUED
    )
    assert (
        WorkflowStateMachine.transition(WorkflowState.QUEUED, WorkflowState.RUNNING)
        == WorkflowState.RUNNING
    )
    assert (
        WorkflowStateMachine.transition(WorkflowState.RUNNING, WorkflowState.COMPLETED)
        == WorkflowState.COMPLETED
    )

    # Self transition no-op
    assert (
        WorkflowStateMachine.transition(WorkflowState.RUNNING, WorkflowState.RUNNING)
        == WorkflowState.RUNNING
    )

    # Invalid transitions
    with pytest.raises(InvalidStateTransitionError):
        WorkflowStateMachine.transition(WorkflowState.PENDING, WorkflowState.RUNNING)

    with pytest.raises(InvalidStateTransitionError):
        WorkflowStateMachine.transition(WorkflowState.COMPLETED, WorkflowState.FAILED)


def test_scheduler_ordering() -> None:
    """Verify scheduler resolves execution groups in dependency-respecting order."""
    plan = ExecutionPlan(
        execution_id="plan-123",
        schema_hash="hash-123",
        execution_groups=[["users"], ["posts"], ["comments"]],
        ordered_tables=["users", "posts", "comments"],
        dependency_levels={"users": 0, "posts": 1, "comments": 2},
        estimated_complexity="low",
        estimated_execution_time=1.0,
        warnings=[],
        planner_version="1.0.0",
        generated_at="2026-06-27T00:00:00",
        estimated_total_duration=1.0,
        estimated_peak_memory=32.0,
        estimated_parallel_workers=1,
        estimated_llm_cost=0.015,
        estimated_generation_cost=0.017,
        planning_confidence=1.0,
        cost_estimate=ExecutionCostEstimate(
            estimated_duration_seconds=1.0,
            estimated_memory_mb=16.0,
            estimated_cpu_weight=0.1,
            estimated_io_weight=0.1,
            estimated_complexity_score=1.0,
            estimated_parallelism=1,
            estimated_llm_calls=3,
            estimated_llm_cost=0.015,
            confidence=1.0,
        ),
        statistics=PlanningStatistics(
            table_count=3,
            relationship_count=2,
            dependency_depth=3,
            execution_groups=3,
            independent_groups=1,
            cyclic_dependencies_detected=False,
            isolated_tables=[],
        ),
    )

    scheduler = WorkflowScheduler(plan)
    assert scheduler.has_more_groups() is True
    assert scheduler.next_group() == ["users"]
    assert scheduler.next_group() == ["posts"]
    assert scheduler.next_group() == ["comments"]
    assert scheduler.has_more_groups() is False

    with pytest.raises(IndexError):
        scheduler.next_group()


def test_progress_tracker() -> None:
    """Verify progress tracker updates counts and progress percentage accurately."""
    tracker = WorkflowProgressTracker(total_groups=4)
    prog = tracker.update(completed=2, failed=0, running=1)
    assert prog.total_groups == 4
    assert prog.completed_groups == 2
    assert prog.failed_groups == 0
    assert prog.running_groups == 1
    assert prog.progress_percentage == 50.0

    prog2 = tracker.update(completed=4, failed=0, running=0)
    assert prog2.progress_percentage == 100.0


@pytest.mark.asyncio
async def test_retry_policy() -> None:
    """Verify that RetryPolicy retries failed calls up to threshold and sleeps using exponential wait."""
    policy = RetryPolicy(max_retries=2, base_delay_seconds=0.01, backoff_factor=2.0)

    mock_func = AsyncMock()
    mock_func.side_effect = [ValueError("Err1"), ValueError("Err2"), "Success"]

    on_retry_mock = Mock()

    result = await policy.execute_with_retry(mock_func, on_retry_mock)
    assert result == "Success"
    assert mock_func.call_count == 3
    assert on_retry_mock.call_count == 2


@pytest.mark.asyncio
async def test_workflow_engine_success() -> None:
    """Test successful workflow execution to completion."""
    plan = ExecutionPlan(
        execution_id="plan-456",
        schema_hash="hash-456",
        execution_groups=[["logs", "users"], ["posts"]],
        ordered_tables=["logs", "users", "posts"],
        dependency_levels={"logs": 0, "users": 0, "posts": 1},
        estimated_complexity="low",
        estimated_execution_time=1.0,
        warnings=[],
        planner_version="1.0.0",
        generated_at="2026-06-27T00:00:00",
        estimated_total_duration=1.0,
        estimated_peak_memory=32.0,
        estimated_parallel_workers=2,
        estimated_llm_cost=0.01,
        estimated_generation_cost=0.012,
        planning_confidence=1.0,
        cost_estimate=ExecutionCostEstimate(
            estimated_duration_seconds=1.0,
            estimated_memory_mb=16.0,
            estimated_cpu_weight=0.1,
            estimated_io_weight=0.1,
            estimated_complexity_score=1.0,
            estimated_parallelism=2,
            estimated_llm_calls=3,
            estimated_llm_cost=0.015,
            confidence=1.0,
        ),
        statistics=PlanningStatistics(
            table_count=3,
            relationship_count=1,
            dependency_depth=2,
            execution_groups=2,
            independent_groups=2,
            cyclic_dependencies_detected=False,
            isolated_tables=["logs"],
        ),
    )

    engine = WorkflowEngine(plan)

    # Track lifecycle start
    start_triggered = False

    def on_start(_w_id: str) -> None:
        nonlocal start_triggered
        start_triggered = True

    engine.lifecycle.register_on_start(on_start)

    mock_table_executor = AsyncMock()
    result = await engine.execute(execute_table_fn=mock_table_executor)

    assert result.status == WorkflowState.COMPLETED
    assert result.progress.progress_percentage == 100.0
    assert result.statistics.completed_tables == 3
    assert result.statistics.failed_tables == 0
    assert len(result.errors) == 0
    assert start_triggered is True
    assert mock_table_executor.call_count == 3


@pytest.mark.asyncio
async def test_workflow_engine_failure_and_retries() -> None:
    """Verify that a failing task triggers retry loops, and transitions to FAILED when exhausted."""
    plan = ExecutionPlan(
        execution_id="plan-789",
        schema_hash="hash-789",
        execution_groups=[["users"]],
        ordered_tables=["users"],
        dependency_levels={"users": 0},
        estimated_complexity="low",
        estimated_execution_time=1.0,
        warnings=[],
        planner_version="1.0.0",
        generated_at="2026-06-27T00:00:00",
        estimated_total_duration=1.0,
        estimated_peak_memory=32.0,
        estimated_parallel_workers=1,
        estimated_llm_cost=0.005,
        estimated_generation_cost=0.007,
        planning_confidence=1.0,
        cost_estimate=ExecutionCostEstimate(
            estimated_duration_seconds=1.0,
            estimated_memory_mb=16.0,
            estimated_cpu_weight=0.1,
            estimated_io_weight=0.1,
            estimated_complexity_score=1.0,
            estimated_parallelism=1,
            estimated_llm_calls=1,
            estimated_llm_cost=0.005,
            confidence=1.0,
        ),
        statistics=PlanningStatistics(
            table_count=1,
            relationship_count=0,
            dependency_depth=1,
            execution_groups=1,
            independent_groups=1,
            cyclic_dependencies_detected=False,
            isolated_tables=["users"],
        ),
    )

    policy = RetryPolicy(max_retries=1, base_delay_seconds=0.01, backoff_factor=1.0)
    engine = WorkflowEngine(plan, retry_policy=policy)

    mock_fail_executor = AsyncMock()
    mock_fail_executor.side_effect = ValueError("Task population error")

    result = await engine.execute(execute_table_fn=mock_fail_executor)

    assert result.status == WorkflowState.FAILED
    assert result.progress.completed_groups == 0
    assert result.progress.failed_groups == 1
    assert result.statistics.failed_tables == 1
    assert len(result.errors) == 1
    assert "Task population error" in result.errors[0]
    assert mock_fail_executor.call_count == 2  # initial attempt + 1 retry
