# ruff: noqa: ARG001
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.execution.integration import (
    ExecutionIntegrationManager,
    MemoryExecutionAdapter,
    RuntimeExecutionAdapter,
    ToolExecutionAdapter,
    WorkflowExecutionAdapter,
)
from app.agents.execution.models import ExecutionContext
from app.agents.memory.manager import AgentMemoryManager
from app.agents.tools import ToolContext, ToolManager, ToolPermission, ToolRegistry
from app.agents.tools.builtin.library import VariableResolverTool


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-int-1",
        workflow_id="wf-int-1",
        workflow_version="1.0.0",
        plan_id="plan-int-1",
        agent_id="agent-int-1",
        session_id="sess-int-1",
        memory_ref="memory_ref_int",
    )


@pytest.fixture
def mock_memory_manager() -> AgentMemoryManager:
    manager = MagicMock(spec=AgentMemoryManager)
    manager.read = AsyncMock(return_value="val1")
    manager.write = AsyncMock()
    return manager


@pytest.fixture
def mock_tool_manager() -> ToolManager:
    # Use real ToolRegistry and ToolManager with a simple tool to test routing
    registry = ToolRegistry()
    registry.register(VariableResolverTool())
    return ToolManager(registry)


@pytest.mark.asyncio
async def test_workflow_context_loading(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Verify workflow adapter loads contexts from persistence provider."""
    adapter = WorkflowExecutionAdapter()

    # Pre-seed the default job if not present to ensure DB validation passes
    from app.platform.container import get_persistence_provider

    pers = get_persistence_provider()
    import contextlib

    with contextlib.suppress(Exception):
        await pers.create_project("default", "Default Project")
    with contextlib.suppress(Exception):
        await pers.create_job(
            job_id=execution_context.execution_id,
            project_id="default",
            job_type="test",
            status="pending",
        )

    job = await adapter.load_context(
        execution_context.workflow_id, execution_context.execution_id
    )
    assert job is not None
    assert job["id"] == execution_context.execution_id


@pytest.mark.asyncio
async def test_memory_integration_load_and_save(
    execution_context: ExecutionContext, mock_memory_manager: AgentMemoryManager
) -> None:
    """Verify memory adapter reads/writes variables via AgentMemoryManager."""
    adapter = MemoryExecutionAdapter(mock_memory_manager)

    # Load memory
    mem = await adapter.load_memory(
        execution_context.workflow_id,
        execution_context.execution_id,
        execution_context.agent_id,
        ["key1"],
    )
    assert isinstance(mem, dict)
    mock_memory_manager.read.assert_called_once()

    # Save memory
    await adapter.save_variable(
        execution_context.workflow_id,
        execution_context.execution_id,
        execution_context.agent_id,
        "key1",
        "val1",
    )
    from app.agents.memory.models import MemoryType

    mock_memory_manager.write.assert_called_once_with(
        execution_context.workflow_id,
        execution_context.execution_id,
        execution_context.agent_id,
        "session",
        MemoryType.SHORT_TERM,
        "key1",
        "val1",
    )


@pytest.mark.asyncio
async def test_tool_routing_integration(mock_tool_manager: ToolManager) -> None:
    """Verify tool requests route strictly through the ToolManager with permissions."""
    adapter = ToolExecutionAdapter(mock_tool_manager)
    context = ToolContext(workflow_id="wf-1", execution_id="exec-1", agent_id="agent-1")

    inputs = {"expression": "hello $workflow_id"}
    res = await adapter.invoke_tool(
        tool_id="variable-resolver",
        inputs=inputs,
        context=context,
        granted_permissions=[ToolPermission.READ],
    )
    assert res.success is True
    assert res.outputs["resolved"] == "hello wf-1"


@pytest.mark.asyncio
async def test_runtime_health_integration() -> None:
    """Verify runtime adapter resolves health state diagnostics."""
    adapter = RuntimeExecutionAdapter()
    healthy = adapter.check_health()
    # Connection pool must be healthy in test setup
    assert healthy is True


@pytest.mark.asyncio
async def test_integration_manager_synchronization(
    setup_test_database: Any,
    execution_context: ExecutionContext,
    mock_memory_manager: AgentMemoryManager,
    mock_tool_manager: ToolManager,
) -> None:
    """Verify context sync maps across runtime checks, workflows, and memory states."""
    # Pre-seed the default job if not present to ensure DB validation passes
    from app.platform.container import get_persistence_provider

    pers = get_persistence_provider()
    import contextlib

    with contextlib.suppress(Exception):
        await pers.create_project("default", "Default Project")
    with contextlib.suppress(Exception):
        await pers.create_job(
            job_id=execution_context.execution_id,
            project_id="default",
            job_type="test",
            status="pending",
        )

    manager = ExecutionIntegrationManager(mock_memory_manager, mock_tool_manager)

    variables = {"status": "running", "step": "sync"}
    res = await manager.synchronize_context(execution_context, variables)

    assert res.success is True
    assert "status" in res.synchronized_keys
    assert "step" in res.synchronized_keys

    # Check metrics
    metrics = manager.get_metrics()
    assert metrics["runtime_lookups"] == 1
    assert metrics["workflow_integrations"] == 1
    assert metrics["memory_lookups"] == 1
    assert metrics["memory_updates"] == 2
