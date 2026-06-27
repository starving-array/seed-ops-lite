"""Strongly typed models for the Workflow Engine."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    """Workflow execution states."""

    PENDING = "pending"
    VALIDATED = "validated"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class WorkflowProgress(BaseModel):
    """Progress tracking for workflow execution."""

    total_groups: int = Field(
        default=0, description="Total execution groups in the plan."
    )
    completed_groups: int = Field(
        default=0, description="Number of successfully completed execution groups."
    )
    failed_groups: int = Field(
        default=0, description="Number of failed execution groups."
    )
    running_groups: int = Field(
        default=0, description="Number of currently running execution groups."
    )
    progress_percentage: float = Field(
        default=0.0, description="Percentage of execution progress (0.0 to 100.0)."
    )


class WorkflowEvent(BaseModel):
    """Event emitted during workflow execution."""

    event_id: str = Field(..., description="UUID identifying this specific event.")
    workflow_id: str = Field(..., description="UUID identifying the active workflow.")
    timestamp: str = Field(..., description="ISO 8601 timestamp string.")
    event_type: str = Field(..., description="Classification category of the event.")
    message: str = Field(..., description="Descriptive log message.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context metadata."
    )


class WorkflowStatistics(BaseModel):
    """Statistics consolidated during workflow execution."""

    total_tables: int = Field(
        default=0, description="Total count of tables to populate."
    )
    completed_tables: int = Field(
        default=0, description="Number of tables successfully populated."
    )
    failed_tables: int = Field(
        default=0, description="Number of tables that failed to populate."
    )
    total_duration_ms: float = Field(
        default=0.0, description="Actual execution duration in milliseconds."
    )
    llm_calls_made: int = Field(default=0, description="Number of LLM calls executed.")
    llm_cost_accumulated: float = Field(
        default=0.0, description="Accumulated LLM API cost in USD."
    )


class WorkflowResult(BaseModel):
    """Final output generated on workflow termination."""

    workflow_id: str = Field(..., description="UUID of the workflow.")
    status: WorkflowState = Field(
        ..., description="Final status state of the workflow."
    )
    progress: WorkflowProgress = Field(..., description="Final progress metrics.")
    statistics: WorkflowStatistics = Field(
        ..., description="Workflow execution statistics."
    )
    events: list[WorkflowEvent] = Field(
        default_factory=list, description="Chronological list of all workflow events."
    )
    errors: list[str] = Field(
        default_factory=list, description="List of error messages encountered."
    )


class Workflow(BaseModel):
    """Representing an active workflow run instance."""

    workflow_id: str = Field(
        ..., description="UUID identifying this workflow execution."
    )
    execution_id: str = Field(
        ..., description="UUID linking to the source ExecutionPlan."
    )
    state: WorkflowState = Field(
        default=WorkflowState.PENDING, description="Current workflow state."
    )
    progress: WorkflowProgress = Field(
        default_factory=WorkflowProgress, description="Active progress tracker."
    )
    statistics: WorkflowStatistics = Field(
        default_factory=WorkflowStatistics, description="Consolidated metrics."
    )
    events: list[WorkflowEvent] = Field(
        default_factory=list, description="Logged workflow events."
    )
