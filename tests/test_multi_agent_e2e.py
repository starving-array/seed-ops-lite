"""Integration tests executing and verifying Multi-Agent Collaboration subsystems end-to-end."""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.collaboration.communication import (
    CommunicationBus,
    DeliveryPolicy,
    MessageEnvelope,
    MessageType,
)
from app.agents.collaboration.delegation import (
    DelegationEngine,
    DelegationPolicy,
)
from app.agents.collaboration.memory import (
    CoordinationManager,
    SharedMemoryManager,
    SynchronizationPolicy,
)
from app.agents.collaboration.models import (
    AgentTask,
    DelegationRequest,
)
from app.agents.collaboration.scheduler import (
    MultiAgentScheduler,
)
from app.agents.framework.manager import AgentManager
from app.agents.framework.models import AgentExecutionResult, AgentLifecycle
from app.agents.framework.registry import AgentRegistry


@pytest.fixture
def mock_agent_registry() -> MagicMock:
    registry = MagicMock(spec=AgentRegistry)

    agent_coord = MagicMock()
    agent_coord.agent_id = "agent-coord"
    agent_coord.capabilities = ["lead"]

    agent_exec = MagicMock()
    agent_exec.agent_id = "agent-exec"
    agent_exec.capabilities = ["run-code"]

    def mock_lookup(aid: str) -> Any:
        res = {
            "agent-coord": agent_coord,
            "agent-exec": agent_exec,
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

    metrics = {
        "agent_availability": True,
        "health_status": "Healthy",
    }
    manager.get_metrics.return_value = metrics

    success_result = AgentExecutionResult(
        execution_id="exec-101",
        status=AgentLifecycle.COMPLETED,
        outputs={"status": "done"},
        errors=[],
        duration=0.01,
        metrics={},
    )
    manager.execute_agent = AsyncMock(return_value=success_result)
    return manager


@pytest.mark.asyncio
async def test_end_to_end_collaboration_scenario(mock_agent_manager: MagicMock) -> None:
    """Verifies delegation, routing, memory workspace, and scheduling working in sync."""

    # 1. Initialize components
    delegation_engine = DelegationEngine(mock_agent_manager)
    communication_bus = CommunicationBus(mock_agent_manager)
    memory_manager = SharedMemoryManager()
    coordination_manager = CoordinationManager(memory_manager)
    scheduler = MultiAgentScheduler()

    # 2. Workspace setup
    workspace_id = "workspace-e2e"
    memory_manager.create_workspace(
        workspace_id=workspace_id,
        workflow_id="wf-e2e",
        execution_id="exec-e2e",
        team_id="team-e2e",
        session_id="sess-e2e",
    )

    # 3. Schedule task with dependencies
    scheduler.schedule_task(
        task_id="t-parent", assigned_agent="agent-coord", priority=5
    )

    scheduler.schedule_task(
        task_id="t-child",
        assigned_agent="agent-exec",
        priority=10,
        dependencies=["t-parent"],
    )

    assert "t-parent" in scheduler.active_assignments
    assert "t-child" not in scheduler.active_assignments  # Queued due to dependency

    # 4. Trigger parent execution & delegation
    task = AgentTask(
        task_id="t-parent",
        title="Verification task",
        assigned_agent_id="agent-coord",
        capabilities_required=["run-code"],
    )
    request = DelegationRequest(
        request_id="req-e2e-1",
        parent_agent_id="agent-coord",
        child_agent_id="agent-coord",
        delegated_task=task,
    )

    del_res = await delegation_engine.delegate_task(
        request=request,
        policy=DelegationPolicy.BEST_CAPABILITY,
        candidates=["agent-coord", "agent-exec"],
    )
    assert del_res.success is True

    # 5. Shared memory update (Intermediate outputs)
    await coordination_manager.acquire_lock(workspace_id, "status", "agent-coord")
    memory_manager.write_variable(
        workspace_id=workspace_id,
        key="status",
        value="parent-completed",
        agent_id="agent-coord",
        policy=SynchronizationPolicy.EXCLUSIVE_WRITE,
    )
    assert memory_manager.read_variable(workspace_id, "status") == "parent-completed"

    # 6. Complete parent task to dispatch queued child
    scheduler.complete_task("t-parent")
    assert "t-child" in scheduler.active_assignments

    # 7. Deliver completion event message
    envelope = MessageEnvelope(
        message_id="msg-e2e-done",
        workflow_id="wf-e2e",
        execution_id="exec-e2e",
        session_id="sess-e2e",
        sender_agent_id="agent-coord",
        receiver_agent_id="agent-exec",
        correlation_id="corr-e2e",
        timestamp=time.time(),
        message_type=MessageType.EVENT,
        payload={"event": "parent-complete"},
    )

    comm_res = await communication_bus.send_message(
        envelope, DeliveryPolicy.ACKNOWLEDGED
    )
    assert comm_res.delivered is True
