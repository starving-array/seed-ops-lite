"""Unit and integration tests verifying Agent Execution Domain Models and State Machine."""

import time

import pytest
from pydantic import ValidationError

from app.agents.execution.models import (
    ExecutionContext,
    ExecutionSession,
    ExecutionState,
    ExecutionStatistics,
    ExecutionTimeline,
)
from app.agents.execution.state_machine import (
    ExecutionStateMachine,
    InvalidStateTransitionError,
)


def test_execution_timeline_durations() -> None:
    """Verify that execution timeline computes durations correctly."""
    now = time.time()
    # Not started yet
    timeline = ExecutionTimeline(created_at=now)
    assert timeline.duration == 0.0

    # Started and completed
    timeline_completed = ExecutionTimeline(
        created_at=now, started_at=now + 1.0, completed_at=now + 5.5
    )
    assert timeline_completed.duration == 4.5

    # Started but not completed (active duration)
    timeline_active = ExecutionTimeline(created_at=now, started_at=now - 2.0)
    assert timeline_active.duration >= 2.0


def test_statistics_average_task_duration() -> None:
    """Verify that statistics calculate averages accurately."""
    stats = ExecutionStatistics(
        task_count=5,
        completed_count=3,
        failed_count=1,
        skipped_count=1,
        retry_count=2,
        execution_duration=9.0,
    )
    assert stats.average_task_duration == 3.0

    # Zero completed tasks returns 0.0 without DivisionByZero
    stats_empty = ExecutionStatistics()
    assert stats_empty.average_task_duration == 0.0


def test_immutable_pydantic_models() -> None:
    """Verify models are frozen (immutable) preventing post-create changes."""
    stats = ExecutionStatistics(task_count=5)
    with pytest.raises((ValidationError, TypeError)):
        stats.task_count = 10


def test_state_machine_valid_transitions() -> None:
    """Verify correct state transition sequences run without errors."""
    # Test valid path: Created -> Initialized -> Queued -> Running -> Completed
    ExecutionStateMachine.validate_transition(
        ExecutionState.CREATED, ExecutionState.INITIALIZED
    )
    ExecutionStateMachine.validate_transition(
        ExecutionState.INITIALIZED, ExecutionState.QUEUED
    )
    ExecutionStateMachine.validate_transition(
        ExecutionState.QUEUED, ExecutionState.RUNNING
    )
    ExecutionStateMachine.validate_transition(
        ExecutionState.RUNNING, ExecutionState.COMPLETED
    )

    # Identical state transition is a valid no-op
    ExecutionStateMachine.validate_transition(
        ExecutionState.RUNNING, ExecutionState.RUNNING
    )


def test_state_machine_invalid_transitions() -> None:
    """Verify state machine blocks disallowed state transition cycles."""
    # Prohibit transitioning backwards or skipping sequences
    with pytest.raises(InvalidStateTransitionError, match="cannot transition"):
        ExecutionStateMachine.validate_transition(
            ExecutionState.CREATED, ExecutionState.RUNNING
        )

    with pytest.raises(InvalidStateTransitionError, match="cannot transition"):
        ExecutionStateMachine.validate_transition(
            ExecutionState.COMPLETED, ExecutionState.RUNNING
        )


def test_model_serialization_deserialization() -> None:
    """Verify Pydantic models serialize to JSON and deserialize cleanly."""
    ctx = ExecutionContext(
        execution_id="exec-123",
        workflow_id="wf-abc",
        workflow_version="1.0.0",
        plan_id="plan-456",
        agent_id="agent-007",
        session_id="sess-xyz",
        memory_ref="mem-link",
    )

    session = ExecutionSession(
        session_id="sess-xyz",
        execution_id="exec-123",
        context=ctx,
        state=ExecutionState.INITIALIZED,
    )

    # Serialize
    data_str = session.model_dump_json()
    assert "exec-123" in data_str
    assert "Initialized" in data_str

    # Deserialization
    parsed = ExecutionSession.model_validate_json(data_str)
    assert parsed.session_id == "sess-xyz"
    assert parsed.context.agent_id == "agent-007"
    assert parsed.state == ExecutionState.INITIALIZED
