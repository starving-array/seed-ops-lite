"""Immutable domain models for the AI Workflow Engine."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkflowLifecycleStatus(str, Enum):
    """Workflow execution and design-time lifecycle states."""

    DRAFT = "Draft"
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class StepType(str, Enum):
    """Supported step types within a workflow plan."""

    PROMPT = "Prompt"
    VALIDATION = "Validation"
    GENERATION = "Generation"
    TRANSFORM = "Transform"
    CONDITION = "Condition"
    LOOP = "Loop"
    MERGE = "Merge"
    EXPORT = "Export"
    HUMAN_APPROVAL = "HumanApproval"


class WorkflowVariable(BaseModel):
    """A typed workflow variable carrying data across steps."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Unique name identifier of the variable.")
    value: Any = Field(..., description="Value stored in the variable.")
    description: str | None = Field(
        default=None, description="Optional description of the variable."
    )


class WorkflowContext(BaseModel):
    """Context container storing variables shared across steps."""

    model_config = ConfigDict(frozen=True)

    variables: dict[str, WorkflowVariable] = Field(
        default_factory=dict, description="Dictionary of variables in this context."
    )


class WorkflowStep(BaseModel):
    """A single logical step of execution in a workflow."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique identifier for the step.")
    name: str = Field(..., description="Human-readable name of the step.")
    description: str | None = Field(
        default=None, description="Detailed description of step purpose."
    )
    type: StepType = Field(..., description="The step execution type.")
    input: dict[str, Any] = Field(
        default_factory=dict, description="Input parameters schema or mapping."
    )
    output: dict[str, Any] = Field(
        default_factory=dict, description="Output parameters schema or mapping."
    )
    dependencies: list[str] = Field(
        default_factory=list, description="IDs of steps this step depends on."
    )
    timeout: int | None = Field(default=None, description="Timeout limit in seconds.")
    retry_count: int = Field(
        default=0, description="Number of times to retry on failure."
    )
    enabled: bool = Field(
        default=True, description="Whether the step is active for execution."
    )


class Workflow(BaseModel):
    """The static definition of a workflow design."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique workflow identifier.")
    name: str = Field(..., description="Name of the workflow.")
    description: str | None = Field(
        default=None, description="Description of workflow purpose."
    )
    steps: list[WorkflowStep] = Field(
        default_factory=list, description="Ordered or linked steps list."
    )
    status: WorkflowLifecycleStatus = Field(
        default=WorkflowLifecycleStatus.DRAFT,
        description="Design-time lifecycle status of workflow.",
    )


class WorkflowExecutionState(BaseModel):
    """The runtime execution state tracking metadata."""

    model_config = ConfigDict(frozen=True)

    started_at: datetime | None = Field(
        default=None, description="Timestamp of execution start."
    )
    finished_at: datetime | None = Field(
        default=None, description="Timestamp of execution end."
    )
    duration: float | None = Field(
        default=None, description="Execution duration in seconds."
    )
    status: WorkflowLifecycleStatus = Field(
        default=WorkflowLifecycleStatus.DRAFT, description="Current execution state."
    )
    current_step: str | None = Field(
        default=None, description="ID of the currently executing step."
    )
    completed_steps: list[str] = Field(
        default_factory=list, description="IDs of successfully completed steps."
    )
    failed_step: str | None = Field(
        default=None, description="ID of the step that failed, if any."
    )
    retry_count: int = Field(
        default=0, description="Total retries attempted during this execution."
    )


class WorkflowExecution(BaseModel):
    """An active runtime run of a workflow."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique execution runtime identifier.")
    workflow_id: str = Field(..., description="Reference to the parent workflow ID.")
    state: WorkflowExecutionState = Field(
        ..., description="Current status state metadata."
    )
    context: WorkflowContext = Field(
        ..., description="Variables context bound to this run."
    )


class WorkflowResult(BaseModel):
    """Final summary outcome of a completed workflow execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(..., description="Reference to the source execution ID.")
    status: WorkflowLifecycleStatus = Field(
        ..., description="Outcome lifecycle status."
    )
    output: dict[str, Any] = Field(
        default_factory=dict, description="Aggregated execution outputs."
    )
    errors: list[str] = Field(
        default_factory=list, description="List of failure messages encountered."
    )
