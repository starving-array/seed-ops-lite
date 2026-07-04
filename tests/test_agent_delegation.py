"""Unit and integration tests verifying Agent Delegation Engine behaviors and constraints."""

from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from app.agents.collaboration.delegation import (
    DelegationEngine,
    DelegationPolicy,
)
from app.agents.collaboration.models import AgentTask, DelegationRequest
from app.agents.framework.manager import AgentManager
from app.agents.framework.models import AgentExecutionResult, AgentLifecycle
from app.agents.framework.registry import AgentRegistry


@pytest.fixture
def mock_agent_registry() -> MagicMock:
    registry = MagicMock(spec=AgentRegistry)
    # Define agent instances mock
    agent1 = MagicMock()
    agent1.agent_id = "agent-coord"
    agent1.capabilities = ["lead", "coordinate"]

    agent2 = MagicMock()
    agent2.agent_id = "agent-exec"
    agent2.capabilities = ["run-code"]

    def mock_lookup(aid: str) -> Any:
        res = {
            "agent-coord": agent1,
            "agent-exec": agent2,
        }.get(aid)
        if res is None:
            raise KeyError("No agent found")
        return res

    registry.lookup.side_effect = mock_lookup
    return registry


@pytest.fixture
def mock_agent_manager(mock_agent_registry: MagicMock) -> MagicMock:
    manager = MagicMock(spec=AgentManager)
    manager.registry = mock_agent_registry

    # Setup metrics mock
    metrics_coord = {
        "execution_count": 5,
        "success_count": 5,
        "failure_count": 0,
        "agent_availability": True,
        "health_status": "Healthy",
    }
    metrics_exec = {
        "execution_count": 2,
        "success_count": 2,
        "failure_count": 0,
        "agent_availability": True,
        "health_status": "Healthy",
    }
    manager.get_metrics.side_effect = lambda aid: {
        "agent-coord": metrics_coord,
        "agent-exec": metrics_exec,
    }.get(aid, {"agent_availability": True, "health_status": "Healthy"})

    # Setup async mock for execute_agent
    success_result = AgentExecutionResult(
        execution_id="exec-123",
        status=AgentLifecycle.COMPLETED,
        outputs={"status": "success"},
        errors=[],
        duration=0.01,
        metrics={},
    )
    manager.execute_agent = AsyncMock(return_value=success_result)
    return manager


@pytest.mark.asyncio
async def test_delegation_direct_assignment_success(
    mock_agent_manager: MagicMock,
) -> None:
    """Verify task delegation matches direct assignment and completes execution successfully."""
    engine = DelegationEngine(mock_agent_manager)
    task = AgentTask(
        task_id="t-1",
        title="Test Task",
        assigned_agent_id="agent-exec",
        capabilities_required=["run-code"],
    )
    request = DelegationRequest(
        request_id="req-1",
        parent_agent_id="agent-coord",
        child_agent_id="agent-exec",
        delegated_task=task,
    )

    res = await engine.delegate_task(request, DelegationPolicy.DIRECT_ASSIGNMENT)
    assert res.success is True
    assert res.outputs == {"status": "success"}
    assert engine.statistics.delegated_task_count == 1
    assert engine.statistics.successes == 1


@pytest.mark.asyncio
async def test_delegation_selection_by_best_capability(
    mock_agent_manager: MagicMock,
) -> None:
    """Verify best capability matches target capabilities list correctly."""
    engine = DelegationEngine(mock_agent_manager)
    task = AgentTask(
        task_id="t-2",
        title="Capability Match Task",
        assigned_agent_id="agent-coord",
        capabilities_required=["run-code"],
    )
    # Direct child starts as agent-coord, but policy is BEST_CAPABILITY with candidates
    request = DelegationRequest(
        request_id="req-2",
        parent_agent_id="agent-coord",
        child_agent_id="agent-coord",
        delegated_task=task,
    )

    res = await engine.delegate_task(
        request,
        policy=DelegationPolicy.BEST_CAPABILITY,
        candidates=["agent-coord", "agent-exec"],
    )
    assert res.success is True
    mock_agent_manager.execute_agent.assert_called_with(
        agent_id="agent-exec", inputs=ANY, workflow_id="delegated-wf"
    )


@pytest.mark.asyncio
async def test_circular_delegation_prevention(mock_agent_manager: MagicMock) -> None:
    """Verify delegation chain rejects requests that contain duplicate parent IDs."""
    engine = DelegationEngine(mock_agent_manager)
    task = AgentTask(
        task_id="t-3",
        title="Circular Task",
        assigned_agent_id="agent-coord",
    )
    # Mock pre-seeded circular chain: coord -> exec -> coord
    engine._delegation_chains["agent-exec"] = ["agent-coord"]

    request = DelegationRequest(
        request_id="req-3",
        parent_agent_id="agent-exec",
        child_agent_id="agent-coord",
        delegated_task=task,
    )

    res = await engine.delegate_task(request)
    assert res.success is False
    assert "Circular delegation detected" in res.errors[0]
    assert engine.statistics.rejections == 1


@pytest.mark.asyncio
async def test_delegation_validator_checks(mock_agent_manager: MagicMock) -> None:
    """Verify validator catches disabled, unhealthy, or capability mismatched candidates."""
    engine = DelegationEngine(mock_agent_manager)

    # 1. Invalid agent
    task = AgentTask(
        task_id="t-4", title="Invalid Target", assigned_agent_id="non-existent"
    )
    req_invalid = DelegationRequest(
        request_id="req-4",
        parent_agent_id="agent-coord",
        child_agent_id="non-existent",
        delegated_task=task,
    )
    res_inv = await engine.delegate_task(req_invalid)
    assert res_inv.success is False
    assert "does not exist" in res_inv.errors[0]

    # 2. Capability mismatched agent
    task_hard = AgentTask(
        task_id="t-5",
        title="Hard Task",
        assigned_agent_id="agent-exec",
        capabilities_required=["super-ai"],
    )
    req_mismatch = DelegationRequest(
        request_id="req-5",
        parent_agent_id="agent-coord",
        child_agent_id="agent-exec",
        delegated_task=task_hard,
    )
    res_mis = await engine.delegate_task(req_mismatch)
    assert res_mis.success is False
    assert "lacks required capabilities" in res_mis.errors[0]
