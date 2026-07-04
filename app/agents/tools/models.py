"""Core data models representing tool definitions, permissions, requests, and contexts."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolPermission(str, Enum):
    """Permissions required by AI Agents or tools to execute operations."""

    READ = "Read"
    WRITE = "Write"
    EXECUTE = "Execute"
    ADMIN = "Admin"
    NETWORK = "Network"
    FILESYSTEM = "Filesystem"
    DATABASE = "Database"
    ENVIRONMENT = "Environment"


class ToolCategory(str, Enum):
    """Categorized classifications of Agent Tools."""

    FILESYSTEM = "Filesystem"
    DATABASE = "Database"
    HTTP = "HTTP"
    WORKFLOW = "Workflow"
    RUNTIME = "Runtime"
    KNOWLEDGE_BASE = "Knowledge Base"
    SEARCH = "Search"
    EXPORT = "Export"
    VALIDATION = "Validation"
    TRANSFORMATION = "Transformation"
    NOTIFICATION = "Notification"
    UTILITY = "Utility"


class ToolCapability(str, Enum):
    """Extensible capabilities provided by concrete tools."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    QUERY_DB = "query_db"
    HTTP_REQUEST = "http_request"
    SEND_MESSAGE = "send_message"
    VALIDATE_SCHEMA = "validate_schema"
    EXPORT_DATA = "export_data"
    UTILITY_RUN = "utility_run"


class ToolMetadata(BaseModel):
    """Identification and permission requirements metadata for tools."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique tool identifier key.")
    name: str = Field(..., description="Human-readable tool description.")
    version: str = Field(..., description="Semantic version string (e.g. 1.0.0).")
    author: str | None = Field(default=None, description="Author identifier.")
    description: str | None = Field(
        default=None, description="Detailed description of tool functionality."
    )
    category: ToolCategory = Field(..., description="Primary classification category.")
    capabilities: list[ToolCapability] = Field(
        default_factory=list, description="List of capabilities provided."
    )
    permissions_required: list[ToolPermission] = Field(
        default_factory=list, description="Required permissions to run."
    )
    creation_time: float = Field(
        default_factory=time.time, description="Creation epoch timestamp."
    )


class ToolDefinition(BaseModel):
    """Static schema wrapping metadata and capabilities."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique identifying string.")
    name: str = Field(..., description="Human-readable tool name.")
    version: str = Field(..., description="Semantic version string.")
    metadata: ToolMetadata = Field(..., description="Tool metadata details.")
    permissions: list[ToolPermission] = Field(
        default_factory=list, description="Access permissions required."
    )


class ToolContext(BaseModel):
    """Execution context detailing workflow and security metadata."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="Target execution workflow ID.")
    execution_id: str = Field(..., description="Target execution run ID.")
    agent_id: str = Field(..., description="Invoking Agent ID.")
    user_context: dict[str, Any] = Field(
        default_factory=dict, description="User credentials / metadata."
    )
    runtime_context: dict[str, Any] = Field(
        default_factory=dict, description="Runtime system environment details."
    )
    memory_context: dict[str, Any] = Field(
        default_factory=dict, description="Agent Memory context snapshot."
    )
    cancellation_token: str | None = Field(
        default=None, description="Task abort/cancellation identifier."
    )


class ToolRequest(BaseModel):
    """Tool invocation payload request."""

    model_config = ConfigDict(frozen=True)

    tool_id: str = Field(..., description="Target tool to trigger.")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Parameter inputs map."
    )
    context: ToolContext = Field(..., description="Context parameters.")


class ToolResponse(BaseModel):
    """Standardized tool response output payload."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(..., description="Whether execution completed cleanly.")
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Standard output variables dictionary."
    )
    errors: list[str] = Field(
        default_factory=list, description="Diagnostic error logs."
    )
    duration: float = Field(..., description="Processing time duration in seconds.")
    warnings: list[str] = Field(default_factory=list, description="Warnings log list.")


class ToolExecution(BaseModel):
    """Tracks active tool execution parameters and settings."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    tool_id: str
    start_time: float
    timeout: float
    max_retries: int


class ToolStatistics(BaseModel):
    """Telemetry metrics tracking execution success, retries, and errors."""

    model_config = ConfigDict(frozen=True)

    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_execution_time: float = 0.0
    retries: int = 0
    timeouts: int = 0
    permission_denials: int = 0
    health_status: bool = True
