"""Workflow Definition Language (DSL) models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VariableType(str, Enum):
    """Supported typed variable categories in the DSL."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    OBJECT = "object"


class DSLStepType(str, Enum):
    """Workflow step execution types supported in the DSL."""

    PROMPT = "Prompt"
    GENERATION = "Generation"
    VALIDATION = "Validation"
    TRANSFORM = "Transform"
    CONDITION = "Condition"
    LOOP = "Loop"
    MERGE = "Merge"
    EXPORT = "Export"
    HUMAN_APPROVAL = "HumanApproval"
    DELAY = "Delay"
    WEBHOOK = "Webhook"


class VariableDefinition(BaseModel):
    """Variable definition within the workflow metadata DSL."""

    model_config = ConfigDict(frozen=True)

    type: VariableType = Field(..., description="The expected type of the variable.")
    default: Any | None = Field(
        default=None, description="Default fallback value if not specified."
    )
    required: bool = Field(
        default=False, description="Whether this variable is required to execute."
    )
    description: str | None = Field(
        default=None, description="Purpose or description of the variable."
    )


class StepDefinition(BaseModel):
    """Step configuration definition in the workflow design DSL."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique step identifier within this workflow.")
    name: str = Field(..., description="Human-readable name of the step.")
    type: DSLStepType = Field(..., description="The step execution type.")
    description: str | None = Field(
        default=None, description="Optional description of the step."
    )
    enabled: bool = Field(default=True, description="Whether this step will execute.")
    timeout: int | None = Field(
        default=None, description="Execution timeout limit in seconds."
    )
    retry_count: int = Field(
        default=0, description="Number of execution retries on failure."
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of step IDs this step directly depends on.",
    )
    input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input variables mapping, literal values, or expressions.",
    )
    output: dict[str, Any] = Field(
        default_factory=dict, description="Outputs structure definition mapping."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom metadata tags."
    )


class WorkflowDefinition(BaseModel):
    """Full workflow schema specification definition."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique workflow definition identifier.")
    schema_version: int = Field(
        default=1, description="Workflow DSL schema format version."
    )
    workflow_version: str = Field(
        default="1.0.0", description="Version of the workflow configuration."
    )
    name: str = Field(..., description="Name of the workflow.")
    description: str | None = Field(
        default=None, description="Workflow purpose description."
    )
    tags: list[str] = Field(default_factory=list, description="Categorization tags.")
    author: str | None = Field(default=None, description="Creator identifier metadata.")
    created_at: str | None = Field(
        default=None, description="ISO timestamp of creation."
    )
    updated_at: str | None = Field(
        default=None, description="ISO timestamp of last update."
    )
    enabled: bool = Field(
        default=True, description="Whether this workflow definition is enabled."
    )
    variables: dict[str, VariableDefinition] = Field(
        default_factory=dict,
        description="Dictionary of typed runtime variables definitions.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom workflow-level metadata."
    )
    steps: list[StepDefinition] = Field(
        default_factory=list, description="List of steps mapping execution order."
    )
