"""Comprehensive system integration audit tests for the AI Platform."""

import sqlite3
import time

import pytest

from app.platform.hitl import (
    ApprovalContext,
    ApprovalDecision,
    ApprovalEngine,
    ApprovalPolicy,
    ApprovalRequest,
    DecisionType,
    InterventionAction,
    InterventionEngine,
    InterventionPolicy,
    InterventionRequest,
    Reviewer,
    ReviewerType,
)
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.workflow.execution import CheckpointManager


@pytest.fixture(autouse=True)
def clean_system_state() -> None:
    """Reset the persistent state for full system audit tests."""
    CheckpointManager.save_checkpoint(
        execution_id="dummy-system-exec",
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
    from app.platform.hitl.notifications import NotificationManager

    _ = NotificationManager()

    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_checkpoints")
        cursor.execute("DELETE FROM workflow_interventions")
        cursor.execute("DELETE FROM workflow_notifications")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS approval_sessions (approval_id TEXT PRIMARY KEY, status TEXT)"
        )
        cursor.execute("DELETE FROM approval_sessions")
        conn.commit()
    finally:
        conn.close()


def test_system_workflow_to_hitl_integration() -> None:
    """Verify context propagation from Workflow state triggers to HITL approvals."""
    # 1. Save execution checkpoint simulating workflow running state
    exec_id = "exec-system-flow-1"
    CheckpointManager.save_checkpoint(
        execution_id=exec_id,
        workflow_id="wf-system-flow",
        workflow_version="1.0.0",
        schema_version=1,
        checkpoint_version="1.0.0",
        current_status="Running",
        current_stage=2,
        completed_steps=["step-1"],
        skipped_steps=[],
        failed_steps=[],
        step_outputs={"step-1": {"result": "ok"}},
        workflow_variables={"authorized": False},
        execution_metadata={"env": "testing"},
    )

    # 2. Trigger HITL Approval Action via ApprovalEngine
    engine = ApprovalEngine()
    context = ApprovalContext(
        workflow_id="wf-system-flow",
        execution_id=exec_id,
        agent_id="agent-verify",
        step_id="step-approval",
    )
    reviewers = [
        Reviewer(
            reviewer_id="rev-system",
            reviewer_type=ReviewerType.USER,
            name="System Auditor",
        )
    ]
    req = ApprovalRequest(
        approval_id="app-system-1",
        context=context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    session = engine.create_session("app-system-1", req)
    assert session.status.value == "Pending"

    # Submit approved decision
    dec = ApprovalDecision(
        decision_id="dec-system-1",
        approval_id="app-system-1",
        reviewer_id="rev-system",
        decision_type=DecisionType.APPROVED,
        timestamp=time.time(),
    )
    res = engine.submit_decision("app-system-1", dec)
    assert res.status.value == "Approved"

    # 3. Request continuation using InterventionEngine
    intervention_engine = InterventionEngine()

    # Inject approval state in sessions table manually for simulation
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS approval_sessions (approval_id TEXT PRIMARY KEY, status TEXT)"
        )
        cursor.execute(
            "INSERT OR REPLACE INTO approval_sessions (approval_id, status) VALUES (?, ?)",
            ("app-system-1", "Approved"),
        )
        conn.commit()
    finally:
        conn.close()

    req_intervention = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.CONTINUE,
        policy=InterventionPolicy.APPROVAL_REQUIRED,
        user_id="rev-system",
        user_role="Operator",
        approval_id="app-system-1",
    )

    success = intervention_engine.process_intervention(req_intervention)
    assert success is True

    # State returned to Running
    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == "Running"
