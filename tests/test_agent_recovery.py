"""Unit and integration tests verifying Agent Execution Recovery, Cancellation, and Retries."""

# ruff: noqa: ARG001
from typing import Any

import pytest

from app.agents.execution.models import ExecutionContext, ExecutionState
from app.agents.execution.recovery import (
    ExecutionCancellationManager,
    ExecutionCheckpointAdapter,
    ExecutionRecoveryManager,
    ExecutionRetryManager,
)


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-rec-1",
        workflow_id="wf-rec-1",
        workflow_version="1.0.0",
        plan_id="plan-rec-1",
        agent_id="agent-rec-1",
        session_id="sess-rec-1",
        memory_ref="memory_ref_rec",
    )


@pytest.mark.asyncio
async def test_checkpoint_creation_and_restoration(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Verify that execution checkpoints can be serialized and deserialized successfully."""
    # Save checkpoint
    ExecutionCheckpointAdapter.save_checkpoint(
        context=execution_context,
        state=ExecutionState.RUNNING,
        completed_tasks=["task1"],
        pending_tasks=["task2"],
        retry_counters={"task2": 1},
        metadata={"phase": "test"},
    )

    # Load checkpoint
    chk = ExecutionCheckpointAdapter.load_checkpoint(execution_context.execution_id)
    assert chk is not None
    assert chk["workflow_id"] == execution_context.workflow_id
    assert chk["current_status"] == ExecutionState.RUNNING.value
    assert chk["completed_steps"] == ["task1"]
    assert chk["failed_steps"] == ["task2"]


@pytest.mark.asyncio
async def test_retry_handling_and_exhaustion() -> None:
    """Verify retry managers count and delay attempts up to exhaustion limits."""
    retry_manager = ExecutionRetryManager()

    # Verify retry check returns True under limit
    assert retry_manager.should_retry("task-1", 1) is True
    assert retry_manager.should_retry("task-1", 2) is True

    # Verify retry check returns False on limit exhaustion
    assert retry_manager.should_retry("task-1", 3) is False

    # Backoff checks
    d1 = retry_manager.get_next_retry_delay("task-1", 1)
    d2 = retry_manager.get_next_retry_delay("task-1", 2)
    assert d2 > d1
    assert d2 == 4.0  # 2.0 * (2 ** (2 - 1))


@pytest.mark.asyncio
async def test_cancellation_propagation() -> None:
    """Verify cancellation managers register sessions and update token statuses."""
    cancellation_manager = ExecutionCancellationManager()
    exec_id = "exec-cancel-test"

    # Default state
    assert cancellation_manager.is_cancelled(exec_id) is False

    # Trigger cancellation
    cancellation_manager.cancel_execution(exec_id)
    assert cancellation_manager.is_cancelled(exec_id) is True


@pytest.mark.asyncio
async def test_recovery_manager_policies_and_failures(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Verify recovery managers invoke policies or report errors when missing state."""
    cancellation_manager = ExecutionCancellationManager()
    recovery_manager = ExecutionRecoveryManager(cancellation_manager)

    # 1. Resume failed (no checkpoint exists)
    res_fail = await recovery_manager.recover_execution(
        "exec-rec-fail", "Resume From Checkpoint"
    )
    assert res_fail.success is False
    assert "No valid checkpoint found" in str(res_fail.error_message)

    # 2. Pre-seed checkpoint
    ExecutionCheckpointAdapter.save_checkpoint(
        context=execution_context,
        state=ExecutionState.RUNNING,
        completed_tasks=["task1"],
        pending_tasks=["task2"],
        retry_counters={"task2": 1},
        metadata={"phase": "test"},
    )

    # 3. Resume successfully
    res_ok = await recovery_manager.recover_execution(
        execution_context.execution_id, "Resume From Checkpoint"
    )
    assert res_ok.success is True
    assert res_ok.restored_stage == 0

    # Verify metrics
    metrics = recovery_manager.get_metrics()
    assert metrics["recoveries"] == 2
    assert metrics["recoveries_failed"] == 1
    assert metrics["checkpoints_restored"] == 1
