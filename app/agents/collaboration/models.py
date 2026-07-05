"""Multi-Agent Collaboration Domain Models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentRole(str, Enum):
    """Multi-Agent system roles metadata definitions."""

    COORDINATOR = "Coordinator"
    PLANNER = "Planner"
    EXECUTOR = "Executor"
    REVIEWER = "Reviewer"
    VALIDATOR = "Validator"
    SPECIALIST = "Specialist"
    OBSERVER = "Observer"


class CollaborationState(str, Enum):
    """Collaboration session lifecycle state definitions."""

    CREATED = "Created"
    PLANNING = "Planning"
    DELEGATING = "Delegating"
    EXECUTING = "Executing"
    SYNCHRONIZING = "Synchronizing"
    WAITING = "Waiting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class AgentMember(BaseModel):
    """Details of a single agent member in a team."""

    model_config = ConfigDict(frozen=True)

    agent_id: str = Field(..., description="Unique identification key of member agent.")
    role: AgentRole = Field(..., description="Assigned role metadata.")
    capabilities: list[str] = Field(
        default_factory=list, description="Supported operations capabilities."
    )


class AgentTeam(BaseModel):
    """Encapsulates a group of cooperating agents."""

    model_config = ConfigDict(frozen=True)

    team_id: str = Field(..., description="Unique team identification key.")
    name: str = Field(..., description="Readable label name.")
    members: list[AgentMember] = Field(
        ..., description="Active member roles mappings list."
    )

    @field_validator("members")
    @classmethod
    def validate_team_integrity(cls, members: list[AgentMember]) -> list[AgentMember]:
        """Validate unique team member ids to prevent duplicates."""
        from app.platform.configuration.settings import platform_settings

        limit = platform_settings.MULTI_AGENT_MAX_TEAM_SIZE
        if len(members) > limit:
            raise ValueError(f"Team size exceeds maximum limit of {limit}.")

        seen_ids = set()
        for member in members:
            if member.agent_id in seen_ids:
                raise ValueError(
                    f"Duplicate team member ID detected: '{member.agent_id}'"
                )
            seen_ids.add(member.agent_id)
        return members


class AgentAssignment(BaseModel):
    """Represents task allocation configuration."""

    model_config = ConfigDict(frozen=True)

    assignment_id: str = Field(..., description="Unique assignment ID.")
    agent_id: str = Field(..., description="Target member agent ID.")
    role: AgentRole = Field(..., description="Target role mapping context.")


class AgentTask(BaseModel):
    """Represents a discrete executable task in multi-agent scope."""

    model_config = ConfigDict(frozen=True)

    task_id: str = Field(..., description="Unique task identification.")
    title: str = Field(..., description="Task title.")
    assigned_agent_id: str = Field(..., description="Target assigned agent ID.")
    priority: int = Field(default=0, description="Task execution priority level.")
    capabilities_required: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    deadline: float | None = Field(default=None)


class DelegationRequest(BaseModel):
    """Models delegation task dispatch details."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(..., description="Unique request identification key.")
    parent_agent_id: str = Field(..., description="Owner parent agent ID.")
    child_agent_id: str = Field(..., description="Delegated child agent ID.")
    delegated_task: AgentTask = Field(
        ..., description="Associated delegated task details."
    )
    assignment_metadata: dict[str, Any] = Field(default_factory=dict)
    retry_policy_reference: str | None = Field(default=None)


class DelegationResult(BaseModel):
    """Captures outcome stats returned by the delegated child execution agent."""

    model_config = ConfigDict(frozen=True)

    request_id: str = Field(..., description="Associated delegation request ID.")
    success: bool = Field(..., description="True if delegation succeeded.")
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class SharedVariable(BaseModel):
    """A key-value state parameter visible to all team members."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(..., description="Variable lookup key.")
    value: Any = Field(..., description="Variable payload value.")


class CollaborationStatistics(BaseModel):
    """Statistical trackers recording multi-agent execution durations."""

    model_config = ConfigDict(frozen=True)

    agent_count: int = 0
    delegated_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    synchronization_count: int = 0
    execution_duration: float = 0.0
    collaboration_duration: float = 0.0


class SharedContext(BaseModel):
    """Aggregates variables shared across execution sessions."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="Workflow execution ID.")
    execution_id: str = Field(..., description="Scope execution run ID.")
    team_id: str = Field(..., description="Target collaborating team ID.")
    shared_variables: dict[str, Any] = Field(
        default_factory=dict, description="Variables mappings."
    )
    shared_memory_references: list[str] = Field(default_factory=list)
    shared_metadata: dict[str, Any] = Field(default_factory=dict)
    shared_outputs: dict[str, Any] = Field(default_factory=dict)
    execution_statistics: CollaborationStatistics = Field(
        default_factory=CollaborationStatistics
    )

    @field_validator("shared_variables")
    @classmethod
    def validate_variables_limit(cls, variables: dict[str, Any]) -> dict[str, Any]:
        """Validate variables volume boundaries using PlatformSettings."""
        from app.platform.configuration.settings import platform_settings

        limit = platform_settings.MULTI_AGENT_MAX_SHARED_VARIABLES
        if len(variables) > limit:
            raise ValueError(
                f"Shared variables count exceeds allowed limit of {limit}."
            )
        return variables


class CollaborationSession(BaseModel):
    """Models a single live multi-agent collaboration cycle session."""

    model_config = ConfigDict(frozen=True)

    session_id: str = Field(..., description="Unique session ID.")
    team: AgentTeam = Field(..., description="Collaborating team instance details.")
    state: CollaborationState = Field(default=CollaborationState.CREATED)
    context: SharedContext = Field(
        ..., description="Shared workspace context metadata."
    )


class CollaborationEvent(BaseModel):
    """Base event contract from which all multi-agent events derive."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(..., description="Unique event identification GUID.")
    session_id: str = Field(..., description="Associated collaboration session ID.")
    timestamp: float = Field(..., description="Epoch occurrence timestamp.")


class TeamCreated(CollaborationEvent):
    """Fired when a team structure is registered."""

    team_id: str
    name: str


class AgentAssigned(CollaborationEvent):
    """Fired when an agent is bound to a task role."""

    agent_id: str
    role: AgentRole


class DelegationStarted(CollaborationEvent):
    """Fired when a task delegation execution starts."""

    request_id: str
    parent_agent_id: str
    child_agent_id: str


class DelegationCompleted(CollaborationEvent):
    """Fired when delegated task outputs are collected."""

    request_id: str
    success: bool


class AgentJoined(CollaborationEvent):
    """Fired when a member joins the active workspace."""

    agent_id: str
    role: AgentRole


class AgentLeft(CollaborationEvent):
    """Fired when a member is unregistered from the workspace."""

    agent_id: str


class SynchronizationStarted(CollaborationEvent):
    """Fired when context variables syncing starts."""

    component: str


class SynchronizationCompleted(CollaborationEvent):
    """Fired when context variables syncing finishes."""

    synchronized_keys: list[str]


class CollaborationCompleted(CollaborationEvent):
    """Fired when team objectives finish successfully."""

    statistics: CollaborationStatistics


class CollaborationFailed(CollaborationEvent):
    """Fired when the team execution lifecycle transitions to Failed."""

    reason: str
    statistics: CollaborationStatistics
