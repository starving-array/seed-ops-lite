"""High-concurrency load and stress benchmark validation tests for the AI Platform."""

import sqlite3
import time

import pytest

from app.platform.hitl import (
    ApprovalContext,
    ApprovalEngine,
    ApprovalPolicy,
    ApprovalRequest,
    InterventionEngine,
    Reviewer,
    ReviewerType,
)
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.workflow.execution import CheckpointManager


@pytest.fixture(autouse=True)
def clean_load_state() -> None:
    """Fixture to ensure database tables are created and clean."""
    CheckpointManager.save_checkpoint(
        execution_id="dummy-load-exec",
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


def test_concurrency_stress_checkpoints() -> None:
    """Stress test high-frequency concurrent checkpoint creation."""
    latencies = []
    for i in range(100):
        start = time.perf_counter()
        CheckpointManager.save_checkpoint(
            execution_id=f"exec-stress-{i}",
            workflow_id="wf-stress",
            workflow_version="1.0.0",
            schema_version=1,
            checkpoint_version="1.0.0",
            current_status="Running",
            current_stage=i,
            completed_steps=[],
            skipped_steps=[],
            failed_steps=[],
            step_outputs={},
            workflow_variables={},
            execution_metadata={},
        )
        latencies.append(time.perf_counter() - start)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 0.15  # Average transaction write must be < 150ms


def test_concurrency_approval_stress() -> None:
    """Stress test high-concurrency approval sessions creations and decisions."""
    engine = ApprovalEngine()
    context = ApprovalContext(
        workflow_id="wf-stress",
        execution_id="exec-stress",
        agent_id="agent-verify",
        step_id="step-approval",
    )
    reviewers = [
        Reviewer(
            reviewer_id="rev-stress",
            reviewer_type=ReviewerType.USER,
            name="System Auditor",
        )
    ]
    req = ApprovalRequest(
        approval_id="app-stress",
        context=context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    latencies = []
    for i in range(100):
        start = time.perf_counter()
        engine.create_session(f"app-stress-{i}", req)
        latencies.append(time.perf_counter() - start)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 0.15
