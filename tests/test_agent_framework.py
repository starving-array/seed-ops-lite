"""Unit and integration tests for the AI Agent Framework & Registry."""

import pytest

from app.agents.framework.interface import Agent
from app.agents.framework.manager import AgentManager, AgentManagerError
from app.agents.framework.models import (
    AgentCapability,
    AgentConfiguration,
    AgentExecutionContext,
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentLifecycle,
    AgentMetadata,
)
from app.agents.framework.registry import AgentRegistry, AgentRegistryError


class MockConcreteAgent(Agent):
    """Mock Agent implementation for framework verification tests."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: list[AgentCapability],
        should_fail_validation: bool = False,
        should_fail_execution: bool = False,
        should_be_unhealthy: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self.agent_name = name
        self.capabilities = capabilities
        self.should_fail_validation = should_fail_validation
        self.should_fail_execution = should_fail_execution
        self.should_be_unhealthy = should_be_unhealthy

        self.initialized = False
        self.cleaned_up = False
        self.cancelled_id: str | None = None
        self.configuration = AgentConfiguration(enabled=True)

    async def initialize(self) -> None:
        self.initialized = True

    async def validate(self) -> bool:
        return not self.should_fail_validation

    async def execute(
        self, request: AgentExecutionRequest, context: AgentExecutionContext
    ) -> AgentExecutionResponse:
        _ = context.execution_id
        if self.should_fail_execution:
            raise Exception("Mock agent execution failure.")

        return AgentExecutionResponse(
            status=AgentLifecycle.COMPLETED,
            outputs={"echo": request.inputs.get("value")},
            duration=0.01,
            metrics={"prompt_tokens": 10},
        )

    async def cancel(self, execution_id: str) -> None:
        self.cancelled_id = execution_id

    async def cleanup(self) -> None:
        self.cleaned_up = True

    async def health(self) -> bool:
        return not self.should_be_unhealthy

    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            id=self.agent_id,
            name=self.agent_name,
            version="1.0.0",
            author="Framework Tests",
            description="Audit framework verification class.",
        )


def test_agent_registry_registration() -> None:
    """Verify clean agent registration and duplicate prevention."""
    registry = AgentRegistry()
    agent_a = MockConcreteAgent("agent-a", "Agent Alpha", [AgentCapability.VALIDATION])
    agent_dup = MockConcreteAgent(
        "agent-a", "Agent Duplicate", [AgentCapability.EXPORT]
    )

    # Standard registration
    registry.register(agent_a)
    assert len(registry.list_agents()) == 1
    assert registry.lookup("agent-a") is agent_a

    # Duplicate registration fails
    with pytest.raises(AgentRegistryError, match="already registered"):
        registry.register(agent_dup)


def test_agent_registry_capability_lookup() -> None:
    """Verify registry filters and returns agents matching registered capabilities."""
    registry = AgentRegistry()
    agent_a = MockConcreteAgent("agent-a", "Agent Alpha", [AgentCapability.VALIDATION])
    agent_b = MockConcreteAgent(
        "agent-b", "Agent Beta", [AgentCapability.EXPORT, AgentCapability.VALIDATION]
    )
    agent_c = MockConcreteAgent(
        "agent-c", "Agent Gamma", [AgentCapability.SECURITY_REVIEW]
    )

    registry.register(agent_a)
    registry.register(agent_b)
    registry.register(agent_c)

    # Lookup validation capability (Alpha + Beta)
    val_agents = registry.lookup_by_capability(AgentCapability.VALIDATION)
    assert len(val_agents) == 2
    assert any(a.metadata().id == "agent-a" for a in val_agents)
    assert any(a.metadata().id == "agent-b" for a in val_agents)

    # Lookup security review capability (Gamma)
    sec_agents = registry.lookup_by_capability(AgentCapability.SECURITY_REVIEW)
    assert len(sec_agents) == 1
    assert sec_agents[0].metadata().id == "agent-c"


@pytest.mark.asyncio
async def test_agent_registry_health_reporting() -> None:
    """Verify health aggregation retrieves status from concrete instances."""
    registry = AgentRegistry()
    agent_healthy = MockConcreteAgent(
        "healthy-agent", "Healthy Agent", [], should_be_unhealthy=False
    )
    agent_sick = MockConcreteAgent(
        "sick-agent", "Sick Agent", [], should_be_unhealthy=True
    )

    registry.register(agent_healthy)
    registry.register(agent_sick)

    health_states = await registry.check_health()
    assert health_states["healthy-agent"] is True
    assert health_states["sick-agent"] is False


@pytest.mark.asyncio
async def test_agent_execution_success() -> None:
    """Verify end-to-end execution lifecycle invokes agent methods and collects metrics."""
    registry = AgentRegistry()
    agent = MockConcreteAgent(
        "runner-agent", "Execution Agent", [AgentCapability.ANALYSIS]
    )
    registry.register(agent)

    manager = AgentManager(registry)
    result = await manager.execute_agent("runner-agent", inputs={"value": "hello"})

    assert result.status == AgentLifecycle.COMPLETED
    assert result.outputs["echo"] == "hello"
    assert agent.initialized is True
    assert agent.cleaned_up is True

    # Check metrics
    metrics = manager.get_metrics("runner-agent")
    assert metrics["execution_count"] == 1
    assert metrics["success_count"] == 1
    assert metrics["failure_count"] == 0
    assert metrics["average_duration"] > 0.0


@pytest.mark.asyncio
async def test_agent_execution_validation_failure() -> None:
    """Verify execution aborts and cleans up when agent validation fails."""
    registry = AgentRegistry()
    agent = MockConcreteAgent(
        "broken-val-agent", "Broken Agent", [], should_fail_validation=True
    )
    registry.register(agent)

    manager = AgentManager(registry)
    with pytest.raises(AgentManagerError, match="validation check failed"):
        await manager.execute_agent("broken-val-agent", inputs={})

    assert agent.initialized is True
    assert agent.cleaned_up is True

    # Check metrics
    metrics = manager.get_metrics("broken-val-agent")
    assert metrics["execution_count"] == 1
    assert metrics["success_count"] == 0
    assert metrics["failure_count"] == 1


@pytest.mark.asyncio
async def test_agent_execution_runtime_failure() -> None:
    """Verify runtime errors during execute are trapped and logged in results."""
    registry = AgentRegistry()
    agent = MockConcreteAgent(
        "runtime-fail-agent", "Fail Agent", [], should_fail_execution=True
    )
    registry.register(agent)

    manager = AgentManager(registry)
    result = await manager.execute_agent("runtime-fail-agent", inputs={})

    assert result.status == AgentLifecycle.FAILED
    assert len(result.errors) == 1
    assert "execution failure" in result.errors[0]
    assert agent.cleaned_up is True

    # Check metrics
    metrics = manager.get_metrics("runtime-fail-agent")
    assert metrics["execution_count"] == 1
    assert metrics["success_count"] == 0
    assert metrics["failure_count"] == 1
