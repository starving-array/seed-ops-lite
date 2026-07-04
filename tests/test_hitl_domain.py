"""Unit tests verifying HITL domain models, validation constraints, and lifecycle state transitions."""

import time

import pytest
from pydantic import ValidationError

from app.platform.hitl.models import (
    ApprovalContext,
    ApprovalLifecycle,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalSession,
    Reviewer,
    ReviewerType,
)


@pytest.fixture
def sample_context() -> ApprovalContext:
    return ApprovalContext(
        workflow_id="wf-101",
        execution_id="exec-101",
        agent_id="agent-coord",
        step_id="step-1",
        request_metadata={"action": "approve-deploy"},
        decision_metadata={},
        audit_metadata={},
        comments=[],
        attachments_metadata=[],
    )


@pytest.fixture
def sample_reviewers() -> list[Reviewer]:
    return [
        Reviewer(
            reviewer_id="rev-1",
            reviewer_type=ReviewerType.USER,
            name="John Doe",
            email="john@seedops.com",
        ),
        Reviewer(
            reviewer_id="rev-2",
            reviewer_type=ReviewerType.USER,
            name="Jane Doe",
            email="jane@seedops.com",
        ),
    ]


def test_immutable_pydantic_models(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify that models use frozen Pydantic configuration to enforce immutability."""
    req = ApprovalRequest(
        approval_id="app-909",
        context=sample_context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    with pytest.raises(ValidationError):
        # Attempt to mutate a frozen model attribute
        req.approval_id = "app-new"


def test_duplicate_reviewer_validation(sample_context: ApprovalContext) -> None:
    """Verify duplicate reviewer entries are rejected by validation constraints."""
    duplicate_reviewers = [
        Reviewer(reviewer_id="rev-1", reviewer_type=ReviewerType.USER, name="John Doe"),
        Reviewer(
            reviewer_id="rev-1",  # Duplicate ID
            reviewer_type=ReviewerType.USER,
            name="John Copy",
        ),
    ]

    with pytest.raises(ValidationError) as exc_info:
        ApprovalRequest(
            approval_id="app-dup",
            context=sample_context,
            policy=ApprovalPolicy.ANY_REVIEWER,
            reviewers=duplicate_reviewers,
            created_at=time.time(),
            expires_at=time.time() + 3600,
        )
    assert "Duplicate reviewer assignments detected." in str(exc_info.value)


def test_state_machine_valid_transitions(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify that sessions permit allowed transitions and block invalid state jumps."""
    req = ApprovalRequest(
        approval_id="app-1",
        context=sample_context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )
    session: ApprovalSession = ApprovalSession(approval_id="app-1", request=req)
    assert session.status.value == ApprovalLifecycle.CREATED.value

    # Created -> Assigned (Allowed)
    session.transition_to(ApprovalLifecycle.ASSIGNED, reason="Reviewers assigned")
    assert session.status.value == ApprovalLifecycle.ASSIGNED.value

    # Assigned -> Pending (Allowed)
    session.transition_to(ApprovalLifecycle.PENDING)
    assert session.status.value == ApprovalLifecycle.PENDING.value

    # Pending -> Approved (Allowed)
    session.transition_to(ApprovalLifecycle.APPROVED)
    assert session.status.value == ApprovalLifecycle.APPROVED.value

    # Approved is a terminal state, trying to transition to Cancelled should fail
    with pytest.raises(ValueError):
        session.transition_to(ApprovalLifecycle.CANCELLED)
