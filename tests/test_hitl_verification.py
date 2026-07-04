"""Verification and integration audit tests for the HITL Platform."""

import sqlite3
import time

import pytest

from app.platform.configuration.settings import platform_settings
from app.platform.hitl import (
    ApprovalContext,
    ApprovalDecision,
    ApprovalEngine,
    ApprovalLifecycle,
    ApprovalPolicy,
    ApprovalRequest,
    DecisionType,
    EscalationManager,
    EscalationPolicy,
    InterventionAction,
    InterventionEngine,
    InterventionPolicy,
    InterventionRequest,
    NotificationManager,
    ReminderPolicy,
    ReminderScheduler,
    Reviewer,
    ReviewerType,
)
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.workflow.execution import CheckpointManager


@pytest.fixture(autouse=True)
def clean_verification_state() -> None:
    """Fixture to reset sqlite DB state for verification."""
    # Ensure tables exist
    CheckpointManager.save_checkpoint(
        execution_id="dummy-verification-exec",
        workflow_id="dummy",
        workflow_version="1.0.0",
        schema_version=1,
        checkpoint_version="1.0.0",
        current_status="Dummy",
        current_stage=0,
        completed_steps=[],
        skipped_steps=[],
        failed_steps=[],
        step_outputs={},
        workflow_variables={},
        execution_metadata={},
    )
    _ = InterventionEngine()
    _ = NotificationManager()

    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_checkpoints")
        cursor.execute("DELETE FROM workflow_interventions")
        cursor.execute("DELETE FROM workflow_notifications")
        # Ensure approval sessions exist for existence validation checks
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS approval_sessions (approval_id TEXT PRIMARY KEY, status TEXT)"
        )
        cursor.execute("DELETE FROM approval_sessions")
        conn.commit()
    finally:
        conn.close()


def create_mock_checkpoint(execution_id: str, status: str = "Running") -> None:
    CheckpointManager.save_checkpoint(
        execution_id=execution_id,
        workflow_id="wf-verification-1",
        workflow_version="1.0.0",
        schema_version=1,
        checkpoint_version="1.0.0",
        current_status=status,
        current_stage=1,
        completed_steps=["step-1"],
        skipped_steps=[],
        failed_steps=["step-2"],
        step_outputs={"step-1": {"output": "val"}},
        workflow_variables={"var1": "abc"},
        execution_metadata={},
    )


def test_verification_approval_lifecycle() -> None:
    """Audit the complete approval workflow consensus and policy checks."""
    engine = ApprovalEngine()
    context = ApprovalContext(
        workflow_id="wf-verification-1",
        execution_id="exec-verification-1",
        agent_id="agent-admin",
        step_id="step-approval",
        request_metadata={"action": "seed-verification"},
        decision_metadata={},
        audit_metadata={},
        comments=[],
        attachments_metadata=[],
    )
    reviewers = [
        Reviewer(reviewer_id="rev-1", reviewer_type=ReviewerType.USER, name="Alice"),
        Reviewer(reviewer_id="rev-2", reviewer_type=ReviewerType.USER, name="Bob"),
    ]

    req = ApprovalRequest(
        approval_id="app-verification-1",
        context=context,
        policy=ApprovalPolicy.ALL_REVIEWERS,
        reviewers=reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    # 1. Start Session
    session = engine.create_session("app-verification-1", req)
    assert session.status == ApprovalLifecycle.PENDING

    # 2. Decision 1
    dec1 = ApprovalDecision(
        decision_id="dec-1",
        approval_id="app-verification-1",
        reviewer_id="rev-1",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-verification-1", dec1)
    assert res.status == ApprovalLifecycle.IN_REVIEW

    # 3. Decision 2 -> Resolves Consensus to APPROVED
    dec2 = ApprovalDecision(
        decision_id="dec-2",
        approval_id="app-verification-1",
        reviewer_id="rev-2",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res2 = engine.submit_decision("app-verification-1", dec2)
    assert res2.status == ApprovalLifecycle.APPROVED


def test_verification_pause_resume_integration() -> None:
    """Verify pause/resume state compliance via InterventionEngine."""
    exec_id = "exec-verification-pause"
    create_mock_checkpoint(exec_id, "Running")

    engine = InterventionEngine()

    # 1. Pause Transition
    req_pause = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="operator-1",
        user_role="Operator",
    )
    assert engine.process_intervention(req_pause) is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == "Paused"

    # 2. Resume Transition
    req_resume = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RESUME,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="operator-1",
        user_role="Operator",
    )
    assert engine.process_intervention(req_resume) is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == "Running"


def test_verification_restart_integration() -> None:
    """Verify restart policy checkpoint restoration."""
    exec_id = "exec-verification-restart"
    create_mock_checkpoint(exec_id, "Failed")

    engine = InterventionEngine()

    req_restart = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RESTART_BEGINNING,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="operator-1",
        user_role="Operator",
    )
    assert engine.process_intervention(req_restart) is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_stage"] == 0
    assert len(checkpoint["completed_steps"]) == 0


def test_verification_notifications_and_escalations() -> None:
    """Verify reminder scheduling and timeout-based escalations."""
    manager = NotificationManager()
    scheduler = ReminderScheduler(manager)
    escalator = EscalationManager(manager)

    # Insert mock approval session to database directly
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO approval_sessions (approval_id, status) VALUES (?, ?)",
            ("app-verification-99", "Pending"),
        )
        conn.commit()
    finally:
        conn.close()

    # 1. Schedule Reminder
    nid = scheduler.schedule_reminder(
        approval_id="app-verification-99",
        target_id="reviewer-1",
        policy=ReminderPolicy.FIXED_INTERVAL,
        reminder_count=0,
    )
    assert nid is not None

    # 2. Check and Trigger Escalation
    escalated = escalator.check_and_escalate(
        approval_id="app-verification-99",
        policy=EscalationPolicy.ESCALATE_TO_ADMIN,
        created_at=time.time() - 2000.0,  # exceeds timeout
    )
    assert escalated is True


def test_verification_config_and_metrics() -> None:
    """Audit settings loading and verify metrics compile correctly."""
    assert platform_settings.HITL_REMINDER_INTERVAL_SECONDS == 300.0
    assert platform_settings.HITL_MAX_REMINDERS == 5
    assert platform_settings.HITL_ESCALATION_TIMEOUT_SECONDS == 1800.0

    manager = NotificationManager()
    metrics = manager.get_metrics()
    assert isinstance(metrics.notifications_created, int)
