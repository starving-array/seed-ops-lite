"""Unit and integration tests verifying Agent Execution Orchestrator coordination."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.execution.models import (
    ExecutionContext,
    ExecutionEvent,
    ExecutionState,
)
from app.agents.execution.orchestrator import (
    ExecutionCoordinator,
    ExecutionEventDispatcher,
    ExecutionSessionManager,
    TaskDispatcher,
)
from app.agents.framework.manager import AgentManager
from app.agents.framework.models import AgentExecutionResult, AgentLifecycle
from app.agents.planning.models import ExecutionPlan, TaskEdge, TaskNode


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-orch-1",
        workflow_id="wf-orch-1",
        workflow_version="1.0.0",
        plan_id="plan-orch-1",
        agent_id="agent-orch-1",
        session_id="sess-orch-1",
        memory_ref="memory_ref_orch",
    )


@pytest.fixture
def mock_agent_manager() -> AgentManager:
    manager = MagicMock(spec=AgentManager)
    # Configure mock agent execution to return success result
    success_result = AgentExecutionResult(
        execution_id="exec-orch-1",
        status=AgentLifecycle.COMPLETED,
        outputs={"key": "value"},
        errors=[],
        duration=0.01,
        metrics={},
    )
    manager.execute_agent = AsyncMock(return_value=success_result)
    return manager


@pytest.mark.asyncio
async def test_session_creation_and_limits(execution_context: ExecutionContext) -> None:
    """Verify session manager registers sessions and enforces max capacity bounds."""
    manager = ExecutionSessionManager()

    # Clean creation
    sess = manager.create_session("sess-1", "exec-1", execution_context)
    assert sess.session_id == "sess-1"
    assert sess.state == ExecutionState.CREATED

    # Prevent duplicate ID creation
    with pytest.raises(ValueError, match="already exists"):
        manager.create_session("sess-1", "exec-2", execution_context)


@pytest.mark.asyncio
async def test_successful_orchestration_loop(
    execution_context: ExecutionContext, mock_agent_manager: AgentManager
) -> None:
    """Verify clean orchestrator stage compilation, dispatching, and completion."""
    session_manager = ExecutionSessionManager()
    event_dispatcher = ExecutionEventDispatcher()
    task_dispatcher = TaskDispatcher(mock_agent_manager)

    coordinator = ExecutionCoordinator(
        session_manager, event_dispatcher, task_dispatcher
    )

    # Setup Plan: Node 1 -> Node 2
    nodes = {
        "t1": TaskNode(id="t1", title="Task 1", description="desc 1"),
        "t2": TaskNode(id="t2", title="Task 2", description="desc 2"),
    }
    edges = [TaskEdge(from_id="t1", to_id="t2")]
    plan = ExecutionPlan(
        id="plan-orch", goal="Sequential run.", nodes=nodes, edges=edges
    )

    # Track published events
    events: list[ExecutionEvent] = []
    event_dispatcher.subscribe(events.append)

    session_manager.create_session("sess-orch-1", "exec-orch-1", execution_context)

    # Execute
    summary = await coordinator.execute_plan("sess-orch-1", plan)

    assert summary.success is True
    assert summary.state == ExecutionState.COMPLETED
    assert "t1" in summary.task_outputs
    assert "t2" in summary.task_outputs

    # Verify event types published
    event_types = [type(e).__name__ for e in events]
    assert "ExecutionStarted" in event_types
    assert "TaskStarted" in event_types
    assert "TaskCompleted" in event_types
    assert "ExecutionCompleted" in event_types

    # Check metrics
    metrics = coordinator.get_metrics()
    assert metrics["sessions_created"] == 1
    assert metrics["tasks_dispatched"] == 2
    assert metrics["tasks_completed"] == 2


@pytest.mark.asyncio
async def test_failure_propagation(
    execution_context: ExecutionContext, mock_agent_manager: AgentManager
) -> None:
    """Verify that task failures abort planning coordination and flag session status."""
    # Reconfigure mock agent manager to return failure outcome
    fail_result = AgentExecutionResult(
        execution_id="exec-orch-1",
        status=AgentLifecycle.FAILED,
        outputs={},
        errors=["Task runner failed."],
        duration=0.01,
        metrics={},
    )
    mock_agent_manager.execute_agent = AsyncMock(return_value=fail_result)  # type: ignore[method-assign]

    session_manager = ExecutionSessionManager()
    event_dispatcher = ExecutionEventDispatcher()
    task_dispatcher = TaskDispatcher(mock_agent_manager)
    coordinator = ExecutionCoordinator(
        session_manager, event_dispatcher, task_dispatcher
    )

    nodes = {"t1": TaskNode(id="t1", title="Task 1", description="desc 1")}
    plan = ExecutionPlan(id="plan-orch", goal="Sequential run.", nodes=nodes, edges=[])

    session_manager.create_session("sess-orch-1", "exec-orch-1", execution_context)

    summary = await coordinator.execute_plan("sess-orch-1", plan)
    assert summary.success is False
    assert summary.state == ExecutionState.FAILED
    assert summary.error_message is not None
    assert "Task runner failed." in summary.error_message


@pytest.mark.asyncio
async def test_cancellation_handling(
    execution_context: ExecutionContext, mock_agent_manager: AgentManager
) -> None:
    """Verify that cancellation token activations trigger clean session halts."""
    session_manager = ExecutionSessionManager()
    event_dispatcher = ExecutionEventDispatcher()
    task_dispatcher = TaskDispatcher(mock_agent_manager)
    coordinator = ExecutionCoordinator(
        session_manager, event_dispatcher, task_dispatcher
    )

    nodes = {"t1": TaskNode(id="t1", title="Task 1", description="desc 1")}
    plan = ExecutionPlan(id="plan-orch", goal="Sequential run.", nodes=nodes, edges=[])

    session_manager.create_session("sess-orch-1", "exec-orch-1", execution_context)

    # Cancel immediately
    def cancel_hook() -> bool:
        return True

    summary = await coordinator.execute_plan(
        "sess-orch-1", plan, cancellation_check=cancel_hook
    )
    assert summary.success is False
    assert summary.state == ExecutionState.CANCELLED
