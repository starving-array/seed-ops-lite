"""Core data models representing agent definitions, configurations, contexts, and execution payloads."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentLifecycle(str, Enum):
    """Lifecycle states of registered AI Agents."""

    REGISTERED = "Registered"
    ENABLED = "Enabled"
    DISABLED = "Disabled"
    BUSY = "Busy"
    READY = "Ready"
    EXECUTING = "Executing"
    COMPLETED = "Completed"
    FAILED = "Failed"


class AgentCapability(str, Enum):
    """Supported extensibility skills and capabilities of AI Agents."""

    SCHEMA_GENERATION = "Schema Generation"
    VALIDATION = "Validation"
    TRANSFORMATION = "Transformation"
    DOCUMENTATION = "Documentation"
    SECURITY_REVIEW = "Security Review"
    CODE_REVIEW = "Code Review"
    TESTING = "Testing"
    EXPORT = "Export"
    ANALYSIS = "Analysis"
    PLANNING = "Planning"


class AgentMetadata(BaseModel):
    """Author and versioning identification metadata."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique identifying string for the agent.")
    name: str = Field(..., description="Human readable name description.")
    version: str = Field(..., description="Semantic version string (e.g. 1.0.0).")
    author: str | None = Field(default=None, description="Author identifier.")
    description: str | None = Field(
        default=None, description="Agent responsibility description."
    )
    creation_time: float = Field(
        default_factory=time.time, description="Creation timestamp."
    )


class AgentConfiguration(BaseModel):
    """Immutable runtime parameters for agent constraints."""

    model_config = ConfigDict(frozen=True)

    timeout: float = Field(default=30.0, description="Step processing timeout limit.")
    retries: int = Field(default=3, description="Maximum retry attempts.")
    temperature: float = Field(
        default=0.0, description="AI model generation temperature."
    )
    model: str | None = Field(
        default=None,
        description="Underlying provider model version (resolved from config if None).",
    )
    maximum_tokens: int = Field(
        default=2048, description="Maximum token response ceiling."
    )
    enabled: bool = Field(default=True, description="Active status toggle flag.")
    priority: int = Field(default=1, description="Execution priority score.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata dictionary."
    )


class AgentDefinition(BaseModel):
    """Aggregated schema mapping metadata and capabilities."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique identifying string for the agent.")
    name: str = Field(..., description="Human readable name description.")
    version: str = Field(..., description="Semantic version string.")
    capabilities: list[AgentCapability] = Field(
        default_factory=list, description="List of registered capabilities."
    )
    configuration: AgentConfiguration = Field(
        default_factory=AgentConfiguration,
        description="Agent configuration parameter limits.",
    )
    metadata: AgentMetadata = Field(..., description="Author and version details.")


class AgentExecutionRequest(BaseModel):
    """Client requested inputs mapped to start an agent step execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(..., description="Tracking code reference.")
    workflow_id: str = Field(..., description="Target execution workflow context.")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Step input variables mapping."
    )
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Pre-loaded runtime context variables."
    )


class AgentExecutionContext(BaseModel):
    """Scoped execution session variables carrying history state across runs."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(..., description="Unique execution UUID mapping.")
    workflow_id: str = Field(..., description="Associated workflow ID.")
    workflow_version: str = Field(..., description="Workflow version string.")
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Workflow typed variables state."
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input variables mapping."
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Output variables mapping."
    )
    runtime_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Subsystem runtime metrics."
    )
    execution_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata tags."
    )


class AgentExecutionResponse(BaseModel):
    """Internal step completion payload return schema."""

    model_config = ConfigDict(frozen=True)

    status: AgentLifecycle = Field(..., description="Outcome status flag.")
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Output dictionary payload."
    )
    duration: float = Field(..., description="Processing time elapsed in seconds.")
    warnings: list[str] = Field(default_factory=list, description="Warnings log list.")
    errors: list[str] = Field(
        default_factory=list, description="Encountered execution errors."
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Subsystem metrics log."
    )


class AgentExecutionResult(BaseModel):
    """Client facing final execution report."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(..., description="Associated run execution ID.")
    status: AgentLifecycle = Field(..., description="Final processing state.")
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Final output values mapping."
    )
    errors: list[str] = Field(
        default_factory=list, description="Diagnostic errors list."
    )
    duration: float = Field(
        ..., description="Total execution processing duration in seconds."
    )
    metrics: dict[str, Any] = Field(default_factory=dict, description="Telemetry logs.")
