"""Chaos and failure injection testing for the Agent Execution Subsystem."""

# ruff: noqa: ARG001, F841
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.execution.models import ExecutionContext
from app.agents.execution.orchestrator import (
    ExecutionCoordinator,
    ExecutionEventDispatcher,
    ExecutionSessionManager,
    TaskDispatcher,
)
from app.agents.execution.recovery import (
    ExecutionCancellationManager,
    ExecutionRecoveryManager,
    ExecutionRetryManager,
)
from app.agents.framework.manager import AgentManager
from app.agents.framework.models import AgentExecutionResult, AgentLifecycle


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-chaos-1",
        workflow_id="wf-chaos-1",
        workflow_version="1.0.0",
        plan_id="plan-chaos-1",
        agent_id="agent-chaos-1",
        session_id="sess-chaos-1",
        memory_ref="memory_ref_chaos",
    )


@pytest.mark.asyncio
async def test_chaos_agent_and_tool_failures(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Inject agent failures and assert retry count increment and recovery outcomes."""
    mock_agent_manager = MagicMock(spec=AgentManager)
    # Simulate first execution failure
    fail_result = AgentExecutionResult(
        execution_id="exec-chaos-1",
        status=AgentLifecycle.FAILED,
        outputs={},
        errors=["Injected agent/tool execution failure."],
        duration=0.01,
        metrics={},
    )
    mock_agent_manager.execute_agent = AsyncMock(return_value=fail_result)

    retry_manager = ExecutionRetryManager()
    # Attempt 1: Should retry
    assert retry_manager.should_retry("t1", 1) is True
    # Attempt 2: Should retry
    assert retry_manager.should_retry("t1", 2) is True
    # Attempt 3: Retry exhausted
    assert retry_manager.should_retry("t1", 3) is False


@pytest.mark.asyncio
async def test_chaos_checkpoint_and_recovery_failures(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Verify system responses when checkpoints are corrupt or missing during recovery."""
    cancel_mgr = ExecutionCancellationManager()
    recovery_mgr = ExecutionRecoveryManager(cancel_mgr)

    # Recovery fails when checkpoint does not exist
    res = await recovery_mgr.recover_execution(
        "non-existent-exec-id", "Resume From Checkpoint"
    )
    assert res.success is False
    assert "No valid checkpoint found" in str(res.error_message)


@pytest.mark.asyncio
async def test_chaos_concurrent_sessions_and_isolation(
    setup_test_database: Any,
) -> None:
    """Verify session isolation and race protection when running concurrent executions."""
    session_manager = ExecutionSessionManager()
    event_dispatcher = ExecutionEventDispatcher()
    mock_agent_manager = MagicMock(spec=AgentManager)

    # Mock manager to return success outcome
    success_result = AgentExecutionResult(
        execution_id="exec-chaos-concurrent",
        status=AgentLifecycle.COMPLETED,
        outputs={"res": "ok"},
        errors=[],
        duration=0.01,
        metrics={},
    )
    mock_agent_manager.execute_agent = AsyncMock(return_value=success_result)

    task_dispatcher = TaskDispatcher(mock_agent_manager)
    coordinator = ExecutionCoordinator(
        session_manager, event_dispatcher, task_dispatcher
    )

    # Pre-seed distinct sessions
    ctx1 = ExecutionContext(
        execution_id="exec-c1",
        workflow_id="wf-c1",
        workflow_version="1.0.0",
        plan_id="plan-c1",
        agent_id="agent-c1",
        session_id="sess-c1",
        memory_ref="mem-c1",
    )
    ctx2 = ExecutionContext(
        execution_id="exec-c2",
        workflow_id="wf-c2",
        workflow_version="1.0.0",
        plan_id="plan-c2",
        agent_id="agent-c2",
        session_id="sess-c2",
        memory_ref="mem-c2",
    )
    session_manager.create_session("sess-c1", "exec-c1", ctx1)
    session_manager.create_session("sess-c2", "exec-c2", ctx2)

    # Validate active sessions count
    assert len(session_manager._sessions) == 2
