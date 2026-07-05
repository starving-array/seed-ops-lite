"""Standard Built-in tools framework definitions."""

from app.agents.tools.builtin.library import (
    DocumentGeneratorTool,
    JsonTransformTool,
    MarkdownExportTool,
    MemoryQueryTool,
    MemorySnapshotTool,
    RuntimeHealthTool,
    SchemaValidationTool,
    TextSearchTool,
    VariableResolverTool,
    WorkflowExecutionTool,
    WorkflowStatusTool,
    WorkflowValidationTool,
)
from app.agents.tools.registry import ToolRegistry


def register_builtin_tools(registry: ToolRegistry) -> None:
    """Helper method to register all first-party built-in tools into a registry.

    Args:
        registry: Target ToolRegistry.
    """
    registry.register(WorkflowStatusTool())
    registry.register(WorkflowExecutionTool())
    registry.register(WorkflowValidationTool())
    registry.register(RuntimeHealthTool())
    registry.register(MemoryQueryTool())
    registry.register(MemorySnapshotTool())
    registry.register(DocumentGeneratorTool())
    registry.register(MarkdownExportTool())
    registry.register(JsonTransformTool())
    registry.register(SchemaValidationTool())
    registry.register(TextSearchTool())
    registry.register(VariableResolverTool())


__all__ = [
    "WorkflowStatusTool",
    "WorkflowExecutionTool",
    "WorkflowValidationTool",
    "RuntimeHealthTool",
    "MemoryQueryTool",
    "MemorySnapshotTool",
    "DocumentGeneratorTool",
    "MarkdownExportTool",
    "JsonTransformTool",
    "SchemaValidationTool",
    "TextSearchTool",
    "VariableResolverTool",
    "register_builtin_tools",
]
