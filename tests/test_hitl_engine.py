"""Unit and integration tests for the Human-in-the-Loop (HITL) Approval Engine."""

import time

import pytest

from app.platform.hitl import (
    ApprovalContext,
    ApprovalDecision,
    ApprovalEngine,
    ApprovalLifecycle,
    ApprovalPolicy,
    ApprovalRequest,
    DecisionType,
    Reviewer,
    ReviewerType,
)


@pytest.fixture
def sample_context() -> ApprovalContext:
    return ApprovalContext(
        workflow_id="wf-hitl",
        execution_id="exec-hitl",
        agent_id="agent-admin",
        step_id="step-hitl",
        request_metadata={"action": "approve-database-seed"},
        decision_metadata={},
        audit_metadata={},
        comments=[],
        attachments_metadata=[],
    )


@pytest.fixture
def sample_reviewers() -> list[Reviewer]:
    return [
        Reviewer(reviewer_id="rev-1", reviewer_type=ReviewerType.USER, name="John Doe"),
        Reviewer(reviewer_id="rev-2", reviewer_type=ReviewerType.USER, name="Jane Doe"),
        Reviewer(
            reviewer_id="rev-3", reviewer_type=ReviewerType.USER, name="Bob Smith"
        ),
    ]


def test_approval_creation_and_any_reviewer_policy(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify ANY_REVIEWER policy completes on first approval or rejection decision."""
    engine = ApprovalEngine()
    req = ApprovalRequest(
        approval_id="app-any",
        context=sample_context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    session = engine.create_session("app-any", req)
    assert session.status.value == ApprovalLifecycle.PENDING.value

    # First reviewer approves
    dec = ApprovalDecision(
        decision_id="dec-1",
        approval_id="app-any",
        reviewer_id="rev-1",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-any", dec)
    assert res.status.value == ApprovalLifecycle.APPROVED.value
    assert res.resolved_at is not None


def test_all_reviewers_policy(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify ALL_REVIEWERS policy requires decisions from all assigned reviewers."""
    engine = ApprovalEngine()
    req = ApprovalRequest(
        approval_id="app-all",
        context=sample_context,
        policy=ApprovalPolicy.ALL_REVIEWERS,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    engine.create_session("app-all", req)

    # 1. First reviewer approves
    dec1 = ApprovalDecision(
        decision_id="dec-1",
        approval_id="app-all",
        reviewer_id="rev-1",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-all", dec1)
    assert res.status.value == ApprovalLifecycle.IN_REVIEW.value

    # 2. Second reviewer approves
    dec2 = ApprovalDecision(
        decision_id="dec-2",
        approval_id="app-all",
        reviewer_id="rev-2",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-all", dec2)
    assert res.status.value == ApprovalLifecycle.IN_REVIEW.value

    # 3. Third reviewer approves -> Resolved to Approved
    dec3 = ApprovalDecision(
        decision_id="dec-3",
        approval_id="app-all",
        reviewer_id="rev-3",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-all", dec3)
    assert res.status.value == ApprovalLifecycle.APPROVED.value


def test_majority_policy(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify MAJORITY policy completes once more than 50% match a decision."""
    engine = ApprovalEngine()
    req = ApprovalRequest(
        approval_id="app-majority",
        context=sample_context,
        policy=ApprovalPolicy.MAJORITY,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    engine.create_session("app-majority", req)

    # 1. First reviewer approves (1 / 3) -> Still IN_REVIEW
    dec1 = ApprovalDecision(
        decision_id="dec-1",
        approval_id="app-majority",
        reviewer_id="rev-1",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-majority", dec1)
    assert res.status.value == ApprovalLifecycle.IN_REVIEW.value

    # 2. Second reviewer approves (2 / 3) -> MAJORITY hit, resolves to Approved
    dec2 = ApprovalDecision(
        decision_id="dec-2",
        approval_id="app-majority",
        reviewer_id="rev-2",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-majority", dec2)
    assert res.status.value == ApprovalLifecycle.APPROVED.value


def test_unanimous_policy_rejection(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify UNANIMOUS policy resolves to Rejected if any single reviewer rejects."""
    engine = ApprovalEngine()
    req = ApprovalRequest(
        approval_id="app-unanimous",
        context=sample_context,
        policy=ApprovalPolicy.UNANIMOUS,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    engine.create_session("app-unanimous", req)

    # 1. First reviewer rejects -> resolves immediately to Rejected
    dec1 = ApprovalDecision(
        decision_id="dec-1",
        approval_id="app-unanimous",
        reviewer_id="rev-1",
        decision_type=DecisionType.REJECTED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-unanimous", dec1)
    assert res.status.value == ApprovalLifecycle.REJECTED.value


def test_first_response_policy(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify FIRST_RESPONSE policy resolves directly to whatever the first answer is."""
    engine = ApprovalEngine()
    req = ApprovalRequest(
        approval_id="app-first",
        context=sample_context,
        policy=ApprovalPolicy.FIRST_RESPONSE,
        reviewers=sample_reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    engine.create_session("app-first", req)

    dec = ApprovalDecision(
        decision_id="dec-first",
        approval_id="app-first",
        reviewer_id="rev-2",
        decision_type=DecisionType.CHANGES_REQUESTED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-first", dec)
    assert res.status.value == ApprovalLifecycle.CHANGES_REQUESTED.value


def test_approval_request_expiration(
    sample_context: ApprovalContext, sample_reviewers: list[Reviewer]
) -> None:
    """Verify that expired request submissions are rejected and marked Expired."""
    engine = ApprovalEngine()
    req = ApprovalRequest(
        approval_id="app-expired",
        context=sample_context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=sample_reviewers,
        created_at=time.time() - 3600,
        expires_at=time.time() - 10,  # Already expired
    )

    engine.create_session("app-expired", req)

    dec = ApprovalDecision(
        decision_id="dec-late",
        approval_id="app-expired",
        reviewer_id="rev-1",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-expired", dec)
    assert res.status.value == ApprovalLifecycle.EXPIRED.value
