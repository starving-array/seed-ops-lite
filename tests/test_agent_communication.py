"""Unit and integration tests verifying Multi-Agent Inter-Agent Communication Bus."""

import time
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

from app.agents.collaboration.communication import (
    CommunicationBus,
    DeliveryPolicy,
    MessageEnvelope,
    MessageType,
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
        outputs={"status": "received"},
        errors=[],
        duration=0.01,
        metrics={},
    )
    manager.execute_agent = AsyncMock(return_value=success_result)
    return manager


@pytest.mark.asyncio
async def test_direct_messaging_success(mock_agent_manager: MagicMock) -> None:
    """Verify routing envelopes directly from sender to recipient completes successfully."""
    bus = CommunicationBus(mock_agent_manager)
    envelope = MessageEnvelope(
        message_id="msg-1",
        workflow_id="wf-1",
        execution_id="exec-1",
        session_id="sess-1",
        sender_agent_id="agent-coord",
        receiver_agent_id="agent-exec",
        correlation_id="corr-1",
        timestamp=time.time(),
        message_type=MessageType.TASK_REQUEST,
        payload={"task": "run"},
    )

    res = await bus.send_message(envelope, DeliveryPolicy.ACKNOWLEDGED)
    assert res.delivered is True
    assert res.acknowledged is True
    assert bus.statistics.messages_sent == 1
    assert bus.statistics.messages_delivered == 1


@pytest.mark.asyncio
async def test_role_and_capability_routing(mock_agent_manager: MagicMock) -> None:
    """Verify messages resolved by capability tag resolve to proper candidate lists."""
    bus = CommunicationBus(mock_agent_manager)
    envelope = MessageEnvelope(
        message_id="msg-2",
        workflow_id="wf-1",
        execution_id="exec-1",
        session_id="sess-1",
        sender_agent_id="agent-coord",
        receiver_agent_id="capability:run-code",
        correlation_id="corr-2",
        timestamp=time.time(),
        message_type=MessageType.TASK_REQUEST,
        payload={"task": "run"},
    )

    candidates = [
        {"agent_id": "agent-coord", "role": "Coordinator"},
        {"agent_id": "agent-exec", "role": "Executor"},
    ]

    res = await bus.send_message(
        envelope,
        policy=DeliveryPolicy.FIRE_AND_FORGET,
        team_candidates=candidates,
    )
    assert res.delivered is True
    # Should resolve to agent-exec because it matches capability 'run-code'
    mock_agent_manager.execute_agent.assert_called_with(
        agent_id="agent-exec",
        inputs=ANY,
        workflow_id="wf-1",
    )


@pytest.mark.asyncio
async def test_idempotent_duplicate_detection(mock_agent_manager: MagicMock) -> None:
    """Verify duplicate message IDs are dropped immediately using caching set checks."""
    bus = CommunicationBus(mock_agent_manager)
    envelope = MessageEnvelope(
        message_id="msg-dup",
        workflow_id="wf-1",
        execution_id="exec-1",
        session_id="sess-1",
        sender_agent_id="agent-coord",
        receiver_agent_id="agent-exec",
        correlation_id="corr-dup",
        timestamp=time.time(),
        message_type=MessageType.EVENT,
    )

    # First send succeeds
    res1 = await bus.send_message(envelope)
    assert res1.delivered is True

    # Second duplicate send returns success immediately with duplicate info warning
    res2 = await bus.send_message(envelope)
    assert res2.delivered is True
    assert "Duplicate message detected" in res2.errors[0]
