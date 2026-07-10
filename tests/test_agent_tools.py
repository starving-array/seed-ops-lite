"""Unit and integration tests for the Agent Tool Calling Framework."""

import asyncio

import pytest

from app.agents.tools.interface import Tool
from app.agents.tools.manager import ToolManager
from app.agents.tools.models import (
    ToolCapability,
    ToolCategory,
    ToolContext,
    ToolMetadata,
    ToolPermission,
    ToolRequest,
    ToolResponse,
)
from app.agents.tools.registry import ToolRegistry, ToolRegistryError


class MockConcreteTool(Tool):
    """Mock Tool implementation for framework verification tests."""

    def __init__(
        self,
        tool_id: str,
        name: str,
        category: ToolCategory,
        capabilities: list[ToolCapability],
        permissions_required: list[ToolPermission],
        should_fail_validation: bool = False,
        should_fail_execution: bool = False,
        should_be_unhealthy: bool = False,
        execution_delay: float = 0.0,
    ) -> None:
        self.tool_id = tool_id
        self.tool_name = name
        self.tool_category = category
        self.tool_capabilities = capabilities
        self.permissions = permissions_required
        self.should_fail_validation = should_fail_validation
        self.should_fail_execution = should_fail_execution
        self.should_be_unhealthy = should_be_unhealthy
        self.execution_delay = execution_delay

        self.initialized = False
        self.cleaned_up = False

    async def initialize(self) -> None:
        self.initialized = True

    async def validate(self, request: ToolRequest) -> bool:  # noqa: ARG002
        return not self.should_fail_validation

    async def execute(
        self,
        request: ToolRequest,
        context: ToolContext,  # noqa: ARG002
    ) -> ToolResponse:
        if self.execution_delay > 0.0:
            await asyncio.sleep(self.execution_delay)

        if self.should_fail_execution:
            raise Exception("Mock tool execution failure.")

        return ToolResponse(
            success=True,
            outputs={"echo": request.inputs.get("param")},
            duration=0.01,
        )

    async def health(self) -> bool:
        return not self.should_be_unhealthy

    async def cleanup(self) -> None:
        self.cleaned_up = True

    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            id=self.tool_id,
            name=self.tool_name,
            version="1.0.0",
            author="Tool Tests",
            description="Verification class.",
            category=self.tool_category,
            capabilities=self.tool_capabilities,
            permissions_required=self.permissions,
        )


def test_tool_registry_registration() -> None:
    """Verify tool registration and duplicate prevention checks."""
    registry = ToolRegistry()
    tool = MockConcreteTool(
        "test-tool", "Test Tool", ToolCategory.UTILITY, [ToolCapability.UTILITY_RUN], []
    )
    dup_tool = MockConcreteTool(
        "test-tool", "Dup Tool", ToolCategory.UTILITY, [ToolCapability.UTILITY_RUN], []
    )

    registry.register(tool)
    assert len(registry.list_tools()) == 1
    assert registry.lookup("test-tool") is tool

    with pytest.raises(ToolRegistryError, match="already registered"):
        registry.register(dup_tool)


def test_tool_registry_lookup_filters() -> None:
    """Verify registry search queries return expected tools by capability and category."""
    registry = ToolRegistry()
    tool_a = MockConcreteTool(
        "tool-a", "Tool A", ToolCategory.FILESYSTEM, [ToolCapability.READ_FILE], []
    )
    tool_b = MockConcreteTool(
        "tool-b",
        "Tool B",
        ToolCategory.DATABASE,
        [ToolCapability.QUERY_DB, ToolCapability.EXPORT_DATA],
        [],
    )

    registry.register(tool_a)
    registry.register(tool_b)

    # Capability lookup
    cap_matches = registry.lookup_by_capability(ToolCapability.READ_FILE)
    assert len(cap_matches) == 1
    assert cap_matches[0].metadata().id == "tool-a"

    # Category lookup
    cat_matches = registry.lookup_by_category(ToolCategory.DATABASE)
    assert len(cat_matches) == 1
    assert cat_matches[0].metadata().id == "tool-b"


@pytest.mark.asyncio
async def test_tool_execution_lifecycle_success() -> None:
    """Verify clean execution runs initialization, validate, execute, and cleanup."""
    registry = ToolRegistry()
    tool = MockConcreteTool(
        "exec-tool", "Executor", ToolCategory.UTILITY, [ToolCapability.UTILITY_RUN], []
    )
    registry.register(tool)

    manager = ToolManager(registry)
    ctx = ToolContext(workflow_id="wf-1", execution_id="ex-1", agent_id="ag-1")

    response = await manager.execute_tool(
        tool_id="exec-tool",
        inputs={"param": "hello"},
        context=ctx,
        granted_permissions=[],
    )

    assert response.success is True
    assert response.outputs["echo"] == "hello"
    assert tool.initialized is True
    assert tool.cleaned_up is True

    # Validate statistics collection
    stats = manager.get_metrics("exec-tool")
    assert stats.execution_count == 1
    assert stats.success_count == 1
    assert stats.failure_count == 0


@pytest.mark.asyncio
async def test_tool_validation_failure() -> None:
    """Verify validation aborts execution early and triggers cleanup."""
    registry = ToolRegistry()
    tool = MockConcreteTool(
        "val-fail-tool",
        "Val Fail",
        ToolCategory.UTILITY,
        [ToolCapability.UTILITY_RUN],
        [],
        should_fail_validation=True,
    )
    registry.register(tool)

    manager = ToolManager(registry)
    ctx = ToolContext(workflow_id="wf-1", execution_id="ex-1", agent_id="ag-1")

    response = await manager.execute_tool(
        tool_id="val-fail-tool", inputs={}, context=ctx, granted_permissions=[]
    )

    assert response.success is False
    assert "validation" in response.errors[0].lower()
    assert tool.initialized is True
    assert tool.cleaned_up is True


@pytest.mark.asyncio
async def test_tool_permission_denial() -> None:
    """Verify missing required permissions blocks execution and reports denial."""
    registry = ToolRegistry()
    tool = MockConcreteTool(
        "secure-tool",
        "Secure Tool",
        ToolCategory.FILESYSTEM,
        [],
        [ToolPermission.WRITE, ToolPermission.FILESYSTEM],
    )
    registry.register(tool)

    manager = ToolManager(registry)
    ctx = ToolContext(workflow_id="wf-1", execution_id="ex-1", agent_id="ag-1")

    # Call with insufficient permissions (WRITE only, missing FILESYSTEM)
    response = await manager.execute_tool(
        tool_id="secure-tool",
        inputs={},
        context=ctx,
        granted_permissions=[ToolPermission.WRITE],
    )

    assert response.success is False
    assert "permission" in response.errors[0].lower()
    assert tool.initialized is False

    stats = manager.get_metrics("secure-tool")
    assert stats.permission_denials == 1


@pytest.mark.asyncio
async def test_tool_timeout_handling() -> None:
    """Verify execution exceeding settings timeout limits terminates safely."""
    registry = ToolRegistry()
    # Configure tool with high delay (10 seconds)
    tool = MockConcreteTool(
        "slow-tool",
        "Slow Tool",
        ToolCategory.UTILITY,
        [],
        [],
        execution_delay=10.0,
    )
    registry.register(tool)

    manager = ToolManager(registry)
    ctx = ToolContext(workflow_id="wf-1", execution_id="ex-1", agent_id="ag-1")

    # Mock timeout setting to a small value (0.01 seconds) to trigger timeout
    from unittest.mock import patch

    with patch(
        "app.platform.configuration.settings.platform_settings.TOOLS_MAX_EXECUTION_TIMEOUT_SECONDS",
        0.01,
    ):
        response = await manager.execute_tool(
            tool_id="slow-tool", inputs={}, context=ctx, granted_permissions=[]
        )

    assert response.success is False
    assert "timed out" in response.errors[0].lower()

    stats = manager.get_metrics("slow-tool")
    assert stats.timeouts == 1
