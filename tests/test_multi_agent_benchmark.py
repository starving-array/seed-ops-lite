"""Performance benchmarks and scalability validation tests for Multi-Agent Collaboration."""

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
    SharedMemoryManager,
    SynchronizationPolicy,
)
from app.agents.collaboration.models import AgentTask, DelegationRequest
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
        duration=0.001,
        metrics={},
    )
    manager.execute_agent = AsyncMock(return_value=success_result)
    return manager


@pytest.mark.asyncio
async def test_delegation_performance_benchmark(mock_agent_manager: MagicMock) -> None:
    """Benchmark task delegation matching and routing latency."""
    engine = DelegationEngine(mock_agent_manager)
    task = AgentTask(
        task_id="t-perf",
        title="Performance task",
        assigned_agent_id="agent-coord",
        capabilities_required=["run-code"],
    )
    request = DelegationRequest(
        request_id="req-perf",
        parent_agent_id="agent-coord",
        child_agent_id="agent-coord",
        delegated_task=task,
    )

    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        res = await engine.delegate_task(
            request=request,
            policy=DelegationPolicy.BEST_CAPABILITY,
            candidates=["agent-coord", "agent-exec"],
        )
        assert res.success is True
    end = time.perf_counter()
    avg_latency = (end - start) / iterations

    # Target average selection latency: < 50ms
    assert avg_latency < 0.05


@pytest.mark.asyncio
async def test_communication_throughput_benchmark(
    mock_agent_manager: MagicMock,
) -> None:
    """Benchmark inter-agent communication bus transmission and processing speed."""
    bus = CommunicationBus(mock_agent_manager)

    envelope = MessageEnvelope(
        message_id="msg-perf",
        workflow_id="wf-perf",
        execution_id="exec-perf",
        session_id="sess-perf",
        sender_agent_id="agent-coord",
        receiver_agent_id="agent-exec",
        correlation_id="corr-perf",
        timestamp=time.time(),
        message_type=MessageType.EVENT,
        payload={"data": "throughput-test"},
    )

    iterations = 100
    start = time.perf_counter()
    for i in range(iterations):
        envelope.message_id = f"msg-perf-{i}"
        res = await bus.send_message(envelope, DeliveryPolicy.FIRE_AND_FORGET)
        assert res.delivered is True
    end = time.perf_counter()

    throughput = iterations / (end - start)
    # Target communication throughput: > 200 messages/sec
    assert throughput > 200.0


@pytest.mark.asyncio
async def test_shared_memory_read_write_latency() -> None:
    """Benchmark workspace state updates and memory synchronization speeds."""
    memory_manager = SharedMemoryManager()
    memory_manager.create_workspace(
        "ws-perf", "wf-perf", "exec-perf", "team-perf", "sess-perf"
    )

    iterations = 1000
    start = time.perf_counter()
    for i in range(iterations):
        memory_manager.write_variable(
            "ws-perf",
            f"key-{i % 10}",
            i,
            "agent-1",
            policy=SynchronizationPolicy.LAST_WRITE_WINS,
        )
    end = time.perf_counter()
    avg_write_latency = (end - start) / iterations

    # Target variable write latency: < 5ms
    assert avg_write_latency < 0.005
