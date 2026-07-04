"""Performance and scalability benchmarks for the HITL Platform."""

import sqlite3
import time

import pytest

from app.platform.hitl import (
    ApprovalContext,
    ApprovalEngine,
    ApprovalPolicy,
    ApprovalRequest,
    InterventionAction,
    InterventionEngine,
    InterventionPolicy,
    InterventionRequest,
    NotificationManager,
    NotificationRequest,
    NotificationType,
    Reviewer,
    ReviewerType,
)
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.workflow.execution import CheckpointManager


@pytest.fixture(autouse=True)
def clean_benchmark_state() -> None:
    """Fixture to ensure database tables are created and clean."""
    # Ensure tables exist
    CheckpointManager.save_checkpoint(
        execution_id="dummy-benchmark-exec",
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
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS approval_sessions (approval_id TEXT PRIMARY KEY, status TEXT)"
        )
        cursor.execute("DELETE FROM approval_sessions")
        conn.commit()
    finally:
        conn.close()


def test_benchmark_approval_creation_performance() -> None:
    """Benchmark approval session creation and reviewer resolution latencies."""
    engine = ApprovalEngine()
    context = ApprovalContext(
        workflow_id="wf-benchmark",
        execution_id="exec-benchmark",
        agent_id="agent-admin",
        step_id="step-approval",
    )
    reviewers = [
        Reviewer(
            reviewer_id=f"rev-{i}", reviewer_type=ReviewerType.USER, name=f"User {i}"
        )
        for i in range(10)
    ]
    req = ApprovalRequest(
        approval_id="app-bench-1",
        context=context,
        policy=ApprovalPolicy.ANY_REVIEWER,
        reviewers=reviewers,
        created_at=time.time(),
        expires_at=time.time() + 3600,
    )

    latencies = []
    for i in range(50):
        start = time.perf_counter()
        engine.create_session(f"app-bench-{i}", req)
        latencies.append(time.perf_counter() - start)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 0.15  # Creation must be fast (< 150ms)


def test_benchmark_pause_resume_performance() -> None:
    """Benchmark intervention engine pause/resume latencies."""
    engine = InterventionEngine()
    latencies_pause = []
    latencies_resume = []

    for i in range(30):
        exec_id = f"exec-bench-pr-{i}"
        CheckpointManager.save_checkpoint(
            execution_id=exec_id,
            workflow_id="wf-benchmark",
            workflow_version="1.0.0",
            schema_version=1,
            checkpoint_version="1.0.0",
            current_status="Running",
            current_stage=1,
            completed_steps=[],
            skipped_steps=[],
            failed_steps=[],
            step_outputs={},
            workflow_variables={},
            execution_metadata={},
        )

        req_pause = InterventionRequest(
            execution_id=exec_id,
            action=InterventionAction.PAUSE,
            policy=InterventionPolicy.MANUAL_ONLY,
            user_id="operator-1",
            user_role="Operator",
        )

        start = time.perf_counter()
        engine.process_intervention(req_pause)
        latencies_pause.append(time.perf_counter() - start)

        req_resume = InterventionRequest(
            execution_id=exec_id,
            action=InterventionAction.RESUME,
            policy=InterventionPolicy.MANUAL_ONLY,
            user_id="operator-1",
            user_role="Operator",
        )

        start = time.perf_counter()
        engine.process_intervention(req_resume)
        latencies_resume.append(time.perf_counter() - start)

    avg_pause = sum(latencies_pause) / len(latencies_pause)
    avg_resume = sum(latencies_resume) / len(latencies_resume)
    assert avg_pause < 0.15
    assert avg_resume < 0.15


def test_benchmark_notification_performance() -> None:
    """Benchmark notification scheduling and dispatch throughput."""
    manager = NotificationManager()

    latencies = []
    for i in range(50):
        req = NotificationRequest(
            approval_id="app-bench-notif",
            notification_type=NotificationType.APPROVAL_REQUESTED,
            target_id=f"reviewer-{i}",
            content="Action required.",
            metadata={"bypass_approval_check": True},
        )

        start = time.perf_counter()
        manager.create_notification(req)
        latencies.append(time.perf_counter() - start)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 0.15
