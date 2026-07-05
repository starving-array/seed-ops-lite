"""Core data models representing task nodes, execution plans, and planning contexts."""

import time
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TaskPriority(str, Enum):
    """Execution priority levels for individual tasks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskComplexity(str, Enum):
    """Estimated sizing/complexity levels for tasks."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    COMPLEX = "complex"


class TaskStatus(str, Enum):
    """Lifecycle execution status of task nodes in a plan."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class PlanningPolicy(str, Enum):
    """Policies dictating structural characteristics of generated plans."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    FASTEST = "fastest"
    LOWEST_COST = "lowest_cost"
    HIGHEST_QUALITY = "highest_quality"


class TaskNode(BaseModel):
    """An atomic unit of work in the generated task execution graph."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique task identifier key.")
    title: str = Field(..., description="Short task title.")
    description: str = Field(
        ..., description="Detailed description of what the task must execute."
    )
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    complexity: TaskComplexity = Field(default=TaskComplexity.MEDIUM)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    required_capabilities: list[str] = Field(
        default_factory=list, description="Capabilities required to run."
    )
    required_tools: list[str] = Field(
        default_factory=list, description="Specific tool IDs needed."
    )
    estimated_duration: float = Field(
        default=1.0, description="Estimated execution time in seconds."
    )

    # Control flow attributes
    is_conditional: bool = Field(default=False)
    condition_expression: str | None = Field(default=None)
    is_loop: bool = Field(default=False)
    loop_expression: str | None = Field(default=None)
    is_optional: bool = Field(default=False)
    requires_approval: bool = Field(
        default=False, description="Manual checkpoint before execution."
    )
    is_recovery_checkpoint: bool = Field(default=False)
    max_retries: int = Field(default=0)


class TaskEdge(BaseModel):
    """Directed dependency link between two task nodes."""

    model_config = ConfigDict(frozen=True)

    from_id: str = Field(..., description="Upstream task node dependency.")
    to_id: str = Field(..., description="Downstream task node block.")


class TaskGroup(BaseModel):
    """A logical set of task nodes designed for grouped execution or tracking."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    task_ids: list[str] = Field(default_factory=list)


class PlanningContext(BaseModel):
    """Scoped metadata detailing environmental variables and constraints during plan generation."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str
    execution_id: str
    agent_id: str
    system_capabilities: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    """Static compiled execution plan matching a Directed Acyclic Graph structure."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique plan UUID identifier.")
    goal: str = Field(..., description="Target objective goal statement.")
    nodes: dict[str, TaskNode] = Field(
        default_factory=dict, description="Nodes index mapping task ID to task details."
    )
    edges: list[TaskEdge] = Field(
        default_factory=list, description="Dependency relationships."
    )
    groups: list[TaskGroup] = Field(
        default_factory=list, description="Logical parallel groupings or stages."
    )
    policy: PlanningPolicy = Field(default=PlanningPolicy.BALANCED)
    creation_time: float = Field(default_factory=time.time)


class PlanningRequest(BaseModel):
    """Payload request containing goal objective specifications."""

    model_config = ConfigDict(frozen=True)

    goal: str = Field(
        ..., description="Primary user objective or goal description statement."
    )
    context: PlanningContext = Field(
        ..., description="Platform and system execution scope context."
    )
    policy: PlanningPolicy = Field(default=PlanningPolicy.BALANCED)


class PlanningResponse(BaseModel):
    """Standardized response output wrapping the generated execution plan."""

    model_config = ConfigDict(frozen=True)

    success: bool = Field(
        ..., description="Whether a plan was generated and validated successfully."
    )
    plan: ExecutionPlan | None = Field(
        default=None, description="The compiled plan DAG."
    )
    errors: list[str] = Field(
        default_factory=list, description="Diagnostic validation or parsing errors."
    )
    duration: float = Field(
        ..., description="Execution planning phase duration in seconds."
    )


class PlanningStatistics(BaseModel):
    """Telemetry metrics tracking planning cycles, errors, and graph complexities."""

    model_config = ConfigDict(frozen=True)

    plans_created: int = 0
    average_planning_time: float = 0.0
    average_task_count: float = 0.0
    average_graph_depth: float = 0.0
    parallelization_ratio: float = 0.0
    critical_path_length: int = 0
    validation_failures: int = 0
