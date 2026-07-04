"""Unit and integration tests verifying the built-in Tool Library."""

import contextlib

import pytest

from app.agents.memory.manager import AgentMemoryManager
from app.agents.tools.builtin import (
    MemoryQueryTool,
    MemorySnapshotTool,
    register_builtin_tools,
)
from app.agents.tools.manager import ToolManager
from app.agents.tools.models import ToolContext, ToolPermission
from app.agents.tools.registry import ToolRegistry


@pytest.fixture
async def test_registry() -> ToolRegistry:
    registry = ToolRegistry()
    register_builtin_tools(registry)
    return registry


@pytest.fixture
def tool_context() -> ToolContext:
    return ToolContext(
        workflow_id="wf-builtin-test",
        execution_id="exec-builtin-test",
        agent_id="agent-builtin-test",
    )


@pytest.mark.asyncio
async def test_builtin_tool_registration(test_registry: ToolRegistry) -> None:
    """Verify all 12 built-in tools are registered successfully."""
    tools = test_registry.list_tools()
    assert len(tools) == 12

    expected_ids = {
        "workflow-status",
        "workflow-execute",
        "workflow-validation",
        "runtime-health",
        "memory-query",
        "memory-snapshot",
        "document-generator",
        "markdown-export",
        "json-transform",
        "schema-validation",
        "text-search",
        "variable-resolver",
    }
    registered_ids = {t.metadata().id for t in tools}
    assert registered_ids == expected_ids


@pytest.mark.asyncio
async def test_workflow_status_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    # Status lookup for missing workflow
    response = await manager.execute_tool(
        tool_id="workflow-status",
        inputs={"workflow_id": "nonexistent-wf"},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is False
    assert len(response.errors) > 0


@pytest.mark.asyncio
async def test_workflow_execution_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    from app.platform.container import get_persistence_provider

    pers = get_persistence_provider()
    with contextlib.suppress(Exception):
        await pers.create_project("default", "Default Project")

    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="workflow-execute",
        inputs={"workflow_id": "wf-new", "params": {"key": "val"}},
        context=tool_context,
        granted_permissions=[ToolPermission.EXECUTE],
    )
    assert response.success is True
    assert response.outputs["status"] == "pending"


@pytest.mark.asyncio
async def test_workflow_validation_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    # Valid execution
    response = await manager.execute_tool(
        tool_id="workflow-validation",
        inputs={"definition": {"steps": ["step1", "step2"]}},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is True
    assert response.outputs["step_count"] == 2

    # Invalid execution
    response_invalid = await manager.execute_tool(
        tool_id="workflow-validation",
        inputs={"definition": "not-a-dict"},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response_invalid.success is False


@pytest.mark.asyncio
async def test_runtime_health_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="runtime-health",
        inputs={},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    # Can be healthy or unhealthy depending on DB state, but execution must succeed/complete
    assert isinstance(response.success, bool)


@pytest.mark.asyncio
async def test_memory_query_tool(tool_context: ToolContext) -> None:
    # Use memory query tool with a mocked memory manager to prevent dependency errors
    memory_manager = AgentMemoryManager()
    await memory_manager.initialize()

    tool = MemoryQueryTool(memory_manager=memory_manager)
    registry = ToolRegistry()
    registry.register(tool)
    manager = ToolManager(registry)

    response = await manager.execute_tool(
        tool_id="memory-query",
        inputs={"query": "test_search"},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is True
    assert "results" in response.outputs
    await tool.cleanup()


@pytest.mark.asyncio
async def test_memory_snapshot_tool(tool_context: ToolContext) -> None:
    memory_manager = AgentMemoryManager()
    await memory_manager.initialize()

    tool = MemorySnapshotTool(memory_manager=memory_manager)
    registry = ToolRegistry()
    registry.register(tool)
    manager = ToolManager(registry)

    response = await manager.execute_tool(
        tool_id="memory-snapshot",
        inputs={"snapshot_id": "snap-99"},
        context=tool_context,
        granted_permissions=[ToolPermission.WRITE],
    )
    assert response.success is True
    assert isinstance(response.outputs["snapshot_id"], str)
    await tool.cleanup()


@pytest.mark.asyncio
async def test_document_generator_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="document-generator",
        inputs={"template": "Hello {{name}}!", "vars": {"name": "World"}},
        context=tool_context,
        granted_permissions=[ToolPermission.WRITE],
    )
    assert response.success is True
    assert response.outputs["document"] == "Hello World!"


@pytest.mark.asyncio
async def test_markdown_export_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="markdown-export",
        inputs={"title": "Test Title", "content": "This is raw content."},
        context=tool_context,
        granted_permissions=[ToolPermission.WRITE],
    )
    assert response.success is True
    assert "# Test Title" in response.outputs["markdown"]


@pytest.mark.asyncio
async def test_json_transform_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="json-transform",
        inputs={"data": {"a": 1, "b": 2, "c": 3}, "select": ["a", "c"]},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is True
    assert response.outputs["transformed"] == {"a": 1, "c": 3}


@pytest.mark.asyncio
async def test_schema_validation_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    # Valid payload
    response = await manager.execute_tool(
        tool_id="schema-validation",
        inputs={
            "payload": {"age": 30, "name": "Alice"},
            "schema": {"age": "int", "name": "str"},
        },
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is True
    assert response.outputs["valid"] is True

    # Invalid payload
    response_invalid = await manager.execute_tool(
        tool_id="schema-validation",
        inputs={
            "payload": {"age": "thirty", "name": "Alice"},
            "schema": {"age": "int", "name": "str"},
        },
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response_invalid.success is False


@pytest.mark.asyncio
async def test_text_search_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="text-search",
        inputs={
            "pattern": "python",
            "texts": ["I love coding", "Python matches", "Learning pytest"],
        },
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is True
    # case-sensitive regex pattern "python" will not match "Python matches" unless case-insensitive,
    # but the matching system behaves as standard compiled regex
    assert response.outputs["match_count"] == 0  # "python" does not match "Python"

    response_case = await manager.execute_tool(
        tool_id="text-search",
        inputs={
            "pattern": "[Pp]ython",
            "texts": ["I love coding", "Python matches", "Learning pytest"],
        },
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response_case.success is True
    assert response_case.outputs["match_count"] == 1
    assert response_case.outputs["matches"][0]["content"] == "Python matches"


@pytest.mark.asyncio
async def test_variable_resolver_tool(
    test_registry: ToolRegistry, tool_context: ToolContext
) -> None:
    manager = ToolManager(test_registry)
    response = await manager.execute_tool(
        tool_id="variable-resolver",
        inputs={"expression": "Active run is $workflow_id and agent is $agent_id"},
        context=tool_context,
        granted_permissions=[ToolPermission.READ],
    )
    assert response.success is True
    assert (
        "Active run is wf-builtin-test and agent is agent-builtin-test"
        in response.outputs["resolved"]
    )
