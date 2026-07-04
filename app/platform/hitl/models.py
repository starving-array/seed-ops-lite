"""Human-in-the-Loop (HITL) Domain Models & Approval Foundation."""

# ruff: noqa: RET508, RET505, S110, PLR0911

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DecisionType(str, Enum):
    """Decision options for human review actions."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ApprovalPolicy(str, Enum):
    """Execution policy rules for finalizing human approvals."""

    ANY_REVIEWER = "ANY_REVIEWER"
    ALL_REVIEWERS = "ALL_REVIEWERS"
    MAJORITY = "MAJORITY"
    UNANIMOUS = "UNANIMOUS"
    FIRST_RESPONSE = "FIRST_RESPONSE"


class ReviewerType(str, Enum):
    """Reviewer classifications."""

    USER = "User"
    ROLE = "Role"
    GROUP = "Group"
    EXTERNAL_REVIEWER = "ExternalReviewer"
    SYSTEM_REVIEWER = "SystemReviewer"


class ApprovalLifecycle(str, Enum):
    """State machine flow states for approval requests."""

    CREATED = "Created"
    ASSIGNED = "Assigned"
    PENDING = "Pending"
    IN_REVIEW = "InReview"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CHANGES_REQUESTED = "ChangesRequested"
    ESCALATED = "Escalated"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"


class Reviewer(BaseModel):
    """Immutable model representing a human reviewer definition."""

    model_config = ConfigDict(frozen=True)

    reviewer_id: str = Field(..., description="Unique reviewer identifier.")
    reviewer_type: ReviewerType = Field(..., description="Type of reviewer.")
    name: str = Field(..., description="Readable name of reviewer.")
    email: str | None = Field(default=None, description="Contact email.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata tags mapping details."
    )


class ReviewerGroup(BaseModel):
    """Group structure containing multiple reviewer assignments."""

    model_config = ConfigDict(frozen=True)

    group_id: str = Field(..., description="Unique group identifier.")
    name: str = Field(..., description="Group label.")
    reviewers: list[Reviewer] = Field(..., description="List of reviewer definitions.")


class ApprovalStep(BaseModel):
    """Single stage review criteria block."""

    model_config = ConfigDict(frozen=True)

    step_id: str = Field(..., description="Unique step identifier.")
    name: str = Field(..., description="Label for this approval step.")
    policy: ApprovalPolicy = Field(
        default=ApprovalPolicy.ANY_REVIEWER, description="Approval requirement policy."
    )
    required_reviewer_ids: list[str] = Field(
        default_factory=list, description="Explicit reviewer IDs."
    )


class ApprovalAssignment(BaseModel):
    """Tracks active assignment matching reviewers to requests."""

    model_config = ConfigDict(frozen=True)

    assignment_id: str = Field(..., description="Unique assignment identifier.")
    approval_id: str = Field(..., description="Associated request ID.")
    reviewer_id: str = Field(..., description="Assigned reviewer identification key.")
    assigned_at: float = Field(..., description="Epoch assignment timestamp.")
    deadline: float | None = Field(default=None, description="Due deadline timestamp.")


class ApprovalDecision(BaseModel):
    """Submitted decision payload from a reviewer."""

    model_config = ConfigDict(frozen=True)

    decision_id: str = Field(..., description="Unique decision ID.")
    approval_id: str = Field(..., description="Associated request ID.")
    reviewer_id: str = Field(..., description="Reviewer key submitting the decision.")
    decision_type: DecisionType = Field(..., description="Decision action selection.")
    timestamp: float = Field(..., description="Submission time.")
    comments: list[str] = Field(default_factory=list, description="Feedback remarks.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Decision metadata."
    )


class ApprovalContext(BaseModel):
    """Execution context scope bindings for the target approval task."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="Workflow execution scope context.")
    execution_id: str = Field(..., description="Execution path isolation identifier.")
    agent_id: str = Field(..., description="Target Agent triggering HITL.")
    step_id: str = Field(..., description="Active step identifier key.")
    request_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Context variables."
    )
    decision_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Decision schema rules."
    )
    audit_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Traceability audit logs."
    )
    comments: list[str] = Field(
        default_factory=list, description="Review feedback comments."
    )
    attachments_metadata: list[dict[str, Any]] = Field(
        default_factory=list, description="Uploaded file information."
    )


class ApprovalRequest(BaseModel):
    """Immutable model encapsulating a HITL validation request details."""

    model_config = ConfigDict(frozen=True)

    approval_id: str = Field(..., description="Unique approval identifier.")
    context: ApprovalContext = Field(..., description="Execution scope constraints.")
    policy: ApprovalPolicy = Field(
        default=ApprovalPolicy.ANY_REVIEWER, description="Resolving consensus strategy."
    )
    reviewers: list[Reviewer] = Field(..., description="Target candidate reviewers.")
    created_at: float = Field(..., description="Epoch creation timestamp.")
    expires_at: float = Field(..., description="Expiration epoch timestamp.")

    @field_validator("reviewers")
    @classmethod
    def validate_reviewers(cls, reviewers: list[Reviewer]) -> list[Reviewer]:
        """Validate unique reviewer assignments and maximum boundaries."""
        from app.platform.configuration.settings import platform_settings

        max_limit = platform_settings.HITL_MAX_REVIEWERS
        if len(reviewers) > max_limit:
            raise ValueError(
                f"Reviewers count '{len(reviewers)}' exceeds allowed limit '{max_limit}'."
            )

        reviewer_ids = [r.reviewer_id for r in reviewers]
        if len(reviewer_ids) != len(set(reviewer_ids)):
            raise ValueError("Duplicate reviewer assignments detected.")

        return reviewers


class ApprovalResponse(BaseModel):
    """Review outcome response payload structure."""

    model_config = ConfigDict(frozen=True)

    approval_id: str = Field(..., description="Associated request ID.")
    status: ApprovalLifecycle = Field(..., description="Resolution lifecycle state.")
    decisions: list[ApprovalDecision] = Field(
        default_factory=list, description="Aggregated decisions."
    )
    resolved_at: float | None = Field(
        default=None, description="Epoch completion timestamp."
    )


class ApprovalHistory(BaseModel):
    """Audit log history tracking status transitions."""

    model_config = ConfigDict(frozen=True)

    approval_id: str = Field(..., description="Target request ID.")
    transitions: list[dict[str, Any]] = Field(
        default_factory=list, description="Chronological log list."
    )


class ApprovalStatistics(BaseModel):
    """Aggregates metrics for the HITL platform."""

    approvals_created: int = 0
    approvals_completed: int = 0
    approvals_rejected: int = 0
    average_approval_time: float = 0.0
    escalations: int = 0
    expired_requests: int = 0
    reviewer_count: int = 0
    decision_distribution: dict[DecisionType, int] = Field(default_factory=dict)


class ApprovalSession(BaseModel):
    """Stateful coordination session for HITL lifecycle operations."""

    approval_id: str = Field(..., description="Unique approval identifier.")
    request: ApprovalRequest = Field(..., description="Definition parameters.")
    status: ApprovalLifecycle = Field(
        default=ApprovalLifecycle.CREATED, description="Active status."
    )
    history: list[dict[str, Any]] = Field(
        default_factory=list, description="Transition lifecycle timeline."
    )

    def transition_to(
        self, new_state: ApprovalLifecycle, reason: str | None = None
    ) -> None:
        """Execute state transition validating valid paths."""
        valid_transitions = {
            ApprovalLifecycle.CREATED: [
                ApprovalLifecycle.ASSIGNED,
                ApprovalLifecycle.PENDING,
                ApprovalLifecycle.CANCELLED,
            ],
            ApprovalLifecycle.ASSIGNED: [
                ApprovalLifecycle.PENDING,
                ApprovalLifecycle.IN_REVIEW,
                ApprovalLifecycle.CANCELLED,
            ],
            ApprovalLifecycle.PENDING: [
                ApprovalLifecycle.IN_REVIEW,
                ApprovalLifecycle.APPROVED,
                ApprovalLifecycle.REJECTED,
                ApprovalLifecycle.EXPIRED,
                ApprovalLifecycle.CANCELLED,
            ],
            ApprovalLifecycle.IN_REVIEW: [
                ApprovalLifecycle.APPROVED,
                ApprovalLifecycle.REJECTED,
                ApprovalLifecycle.CHANGES_REQUESTED,
                ApprovalLifecycle.ESCALATED,
                ApprovalLifecycle.EXPIRED,
                ApprovalLifecycle.CANCELLED,
            ],
            ApprovalLifecycle.CHANGES_REQUESTED: [
                ApprovalLifecycle.PENDING,
                ApprovalLifecycle.IN_REVIEW,
                ApprovalLifecycle.CANCELLED,
            ],
            ApprovalLifecycle.ESCALATED: [
                ApprovalLifecycle.PENDING,
                ApprovalLifecycle.APPROVED,
                ApprovalLifecycle.REJECTED,
                ApprovalLifecycle.CANCELLED,
            ],
            ApprovalLifecycle.APPROVED: [],
            ApprovalLifecycle.REJECTED: [],
            ApprovalLifecycle.EXPIRED: [],
            ApprovalLifecycle.CANCELLED: [],
        }

        current = self.status
        allowed = valid_transitions.get(current, [])
        if new_state not in allowed:
            raise ValueError(
                f"Invalid state transition: Cannot transition from '{current}' to '{new_state}'."
            )

        self.status = new_state
        self.history.append(
            {
                "from_state": current.value,
                "to_state": new_state.value,
                "timestamp": time.time() if hasattr(time, "time") else 0.0,
                "reason": reason,
            }
        )


class ApprovalEvent(BaseModel):
    """System event envelope emitted during HITL lifecycle updates."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(..., description="Unique event identification key.")
    approval_id: str = Field(..., description="Associated request ID.")
    event_type: str = Field(..., description="Event type classification label.")
    timestamp: float = Field(..., description="Epoch timestamp.")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Metadata parameters."
    )
