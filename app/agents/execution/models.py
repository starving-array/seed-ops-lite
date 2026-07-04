"""Execution domain models detailing state structures, telemetry events, contexts, and results."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionState(str, Enum):
    """Execution lifecycle states for agents and tasks."""

    CREATED = "Created"
    INITIALIZED = "Initialized"
    QUEUED = "Queued"
    RUNNING = "Running"
    WAITING = "Waiting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    RECOVERED = "Recovered"


class ExecutionPolicy(str, Enum):
    """Policies dictating behavior when tasks fail or wait for actions."""

    FAIL_FAST = "Fail Fast"
    CONTINUE = "Continue"
    RETRY = "Retry"
    SKIP = "Skip"
    MANUAL_APPROVAL = "Manual Approval"
    RECOVERY = "Recovery"


class ExecutionMetadata(BaseModel):
    """Immutable metadata tracking agent config and run details."""

    model_config = ConfigDict(frozen=True)

    environment: str = Field(default="production")
    tags: list[str] = Field(default_factory=list)
    custom_properties: dict[str, Any] = Field(default_factory=dict)


class ExecutionTimeline(BaseModel):
    """Execution timestamp metrics tracking process milestones."""

    model_config = ConfigDict(frozen=True)

    created_at: float = Field(default_factory=time.time)
    started_at: float | None = Field(default=None)
    completed_at: float | None = Field(default=None)

    @property
    def duration(self) -> float:
        """Calculate total duration of execution in seconds.

        Returns:
            float: Duration value, or 0.0 if not completed or started.
        """
        if self.started_at is None:
            return 0.0
        end = self.completed_at or time.time()
        dur = end - self.started_at
        return max(0.0, dur)


class ExecutionStatistics(BaseModel):
    """Telemetry metrics tracking task execution counts, retries, and timing averages."""

    model_config = ConfigDict(frozen=True)

    task_count: int = Field(default=0, ge=0)
    completed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    checkpoint_count: int = Field(default=0, ge=0)
    execution_duration: float = Field(default=0.0, ge=0.0)

    @property
    def average_task_duration(self) -> float:
        """Calculate average duration per task node run.

        Returns:
            float: Average seconds, or 0.0 if no tasks have completed.
        """
        if self.completed_count == 0:
            return 0.0
        return max(0.0, self.execution_duration / self.completed_count)


class ExecutionContext(BaseModel):
    """Execution context detailing workflow parameters and cancellation tokens."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    workflow_id: str
    workflow_version: str
    plan_id: str
    agent_id: str
    session_id: str
    memory_ref: str
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    cancellation_token_ref: str | None = Field(default=None)


class ExecutionTask(BaseModel):
    """Represents a specific task node run mapping state metadata."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    plan_id: str
    node_id: str
    status: ExecutionState = Field(default=ExecutionState.CREATED)
    error_message: str | None = Field(default=None)
    retry_count: int = Field(default=0, ge=0)
    duration: float = Field(default=0.0, ge=0.0)


class ExecutionResult(BaseModel):
    """Immutable outcome payload mapping execution outputs and statistics."""

    model_config = ConfigDict(frozen=True)

    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = Field(default=None)
    statistics: ExecutionStatistics = Field(default_factory=ExecutionStatistics)
    timeline: ExecutionTimeline = Field(default_factory=ExecutionTimeline)


class ExecutionSession(BaseModel):
    """Active execution session state tracking state transitions."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    execution_id: str
    context: ExecutionContext
    state: ExecutionState = Field(default=ExecutionState.CREATED)
    result: ExecutionResult | None = Field(default=None)
    statistics: ExecutionStatistics = Field(default_factory=ExecutionStatistics)
    timeline: ExecutionTimeline = Field(default_factory=ExecutionTimeline)


# Event Model Hierarchy
class ExecutionEvent(BaseModel):
    """Base model for all agent lifecycle telemetry events."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(..., description="Unique event UUID.")
    timestamp: float = Field(default_factory=time.time)
    execution_id: str
    workflow_id: str
    agent_id: str


class ExecutionCreated(ExecutionEvent):
    """Fired when an execution session is allocated."""

    pass


class ExecutionStarted(ExecutionEvent):
    """Fired when execution begins running."""

    pass


class TaskStarted(ExecutionEvent):
    """Fired when an individual task starts."""

    task_id: str
    node_id: str


class TaskCompleted(ExecutionEvent):
    """Fired when an individual task completes successfully."""

    task_id: str
    node_id: str
    duration: float


class TaskFailed(ExecutionEvent):
    """Fired when a task fails execution."""

    task_id: str
    node_id: str
    error: str
    duration: float


class ExecutionCompleted(ExecutionEvent):
    """Fired when the execution session completes successfully."""

    result: ExecutionResult


class ExecutionFailed(ExecutionEvent):
    """Fired when the execution session fails."""

    error: str
    result: ExecutionResult


class ExecutionCancelled(ExecutionEvent):
    """Fired when an execution is aborted by a cancellation token."""

    reason: str
    result: ExecutionResult


class CheckpointCreated(ExecutionEvent):
    """Fired when a state snapshot checkpoint is written to memory."""

    checkpoint_id: str
    memory_ref: str


class CheckpointRestored(ExecutionEvent):
    """Fired when state is rolled back/rehydrated from a checkpoint."""

    checkpoint_id: str
    memory_ref: str
