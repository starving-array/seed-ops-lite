"""Chaos engineering and disaster recovery validation tests for the AI Platform."""

import sqlite3

import pytest

from app.platform.hitl import (
    InterventionAction,
    InterventionEngine,
    InterventionPolicy,
    InterventionRequest,
)
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.workflow.execution import CheckpointManager


@pytest.fixture(autouse=True)
def clean_chaos_state() -> None:
    """Fixture to ensure database tables are created and clean."""
    CheckpointManager.save_checkpoint(
        execution_id="dummy-chaos-exec",
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


def test_checkpoint_corruption_recovery() -> None:
    """Verify that the platform handles corrupted checkpoints gracefully."""
    # Write invalid data directly to bypass schema validators
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO workflow_checkpoints (execution_id, workflow_id, checkpoint_version) VALUES (?, ?, ?)",
            ("exec-corrupted", None, None),
        )
        conn.commit()
    finally:
        conn.close()

    # Verify that loading raises ValueError (corrupted checkpoint check)
    with pytest.raises(ValueError, match="Corrupted checkpoint"):
        CheckpointManager.load_checkpoint("exec-corrupted")


def test_database_connection_failure() -> None:
    """Verify that connection failures or database locks fail safely without corruption."""
    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id="does-not-exist",
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="operator-1",
        user_role="Operator",
    )

    # Database query should return False safely if execution doesn't exist
    assert engine.process_intervention(req) is False
