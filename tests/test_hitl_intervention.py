"""Unit and integration tests for the Human-in-the-Loop (HITL) Intervention Engine."""

import sqlite3
import time

import pytest

from app.platform.configuration.settings import platform_settings
from app.platform.hitl import (
    ExecutionStateTransition,
    InterventionAction,
    InterventionEngine,
    InterventionPolicy,
    InterventionRequest,
)
from app.workflow.execution import CheckpointManager


@pytest.fixture(autouse=True)
def clean_database_state() -> None:
    """Fixture to ensure checkpoints and interventions tables are truncated/initialized."""
    from app.platform.providers.sqlite_db import sqlite_db_manager

    # Ensure tables exist
    CheckpointManager.save_checkpoint(
        execution_id="dummy-test-exec",
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

    # Initialize interventions table
    _ = InterventionEngine()

    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_checkpoints")
        cursor.execute("DELETE FROM workflow_interventions")
        conn.commit()
    finally:
        conn.close()


def create_dummy_checkpoint(execution_id: str, status: str = "Running") -> None:
    """Helper to save a mock checkpoint."""
    CheckpointManager.save_checkpoint(
        execution_id=execution_id,
        workflow_id="wf-test-123",
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


def test_configuration_loading() -> None:
    """Verify configuration loads properly from PlatformSettings."""
    assert platform_settings.HITL_PAUSE_TIMEOUT_SECONDS == 3600.0
    assert platform_settings.HITL_RESUME_TIMEOUT_SECONDS == 3600.0
    assert platform_settings.HITL_MAX_INTERVENTION_HISTORY == 1000
    assert platform_settings.HITL_CHECKPOINT_RESTART_TIMEOUT_SECONDS == 600.0


def test_pause_execution() -> None:
    """Verify pause transitions state to Paused and saves updated checkpoint."""
    exec_id = "exec-pause"
    create_dummy_checkpoint(exec_id, "Running")

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )

    success = engine.process_intervention(req)
    assert success is True

    # Check updated checkpoint state
    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == ExecutionStateTransition.PAUSED.value
    assert "paused_at" in checkpoint["execution_metadata"]


def test_resume_execution() -> None:
    """Verify resume transitions state from Paused back to Running."""
    exec_id = "exec-resume"
    create_dummy_checkpoint(exec_id, "Paused")

    # Manually inject a paused_at timestamp
    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    checkpoint["execution_metadata"]["paused_at"] = time.time() - 10.0
    CheckpointManager.save_checkpoint(
        execution_id=exec_id,
        workflow_id=checkpoint["workflow_id"],
        workflow_version=checkpoint["workflow_version"],
        schema_version=checkpoint["schema_version"],
        checkpoint_version=checkpoint["checkpoint_version"],
        current_status="Paused",
        current_stage=checkpoint["current_stage"],
        completed_steps=checkpoint["completed_steps"],
        skipped_steps=checkpoint["skipped_steps"],
        failed_steps=checkpoint["failed_steps"],
        step_outputs=checkpoint["step_outputs"],
        workflow_variables=checkpoint["workflow_variables"],
        execution_metadata=checkpoint["execution_metadata"],
    )

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RESUME,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )

    success = engine.process_intervention(req)
    assert success is True

    # Check state returned to Running
    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == ExecutionStateTransition.RUNNING.value


def test_cancel_execution() -> None:
    """Verify cancellation transition and state completion."""
    exec_id = "exec-cancel"
    create_dummy_checkpoint(exec_id, "Running")

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.CANCEL,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )

    success = engine.process_intervention(req)
    assert success is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == ExecutionStateTransition.CANCELLED.value


def test_restart_from_checkpoint() -> None:
    """Verify restarting from last checkpoint is allowed and sets RESTARTED state."""
    exec_id = "exec-restart-cp"
    create_dummy_checkpoint(exec_id, "Failed")

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RESTART_CHECKPOINT,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )

    success = engine.process_intervention(req)
    assert success is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == ExecutionStateTransition.RESTARTED.value
    # Completed steps should remain intact for checkpoint restart
    assert checkpoint["completed_steps"] == ["step-1"]


def test_restart_from_beginning() -> None:
    """Verify restart from beginning resets progress, steps, and outputs."""
    exec_id = "exec-restart-beg"
    create_dummy_checkpoint(exec_id, "Failed")

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RESTART_BEGINNING,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )

    success = engine.process_intervention(req)
    assert success is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert checkpoint["current_status"] == ExecutionStateTransition.RUNNING.value
    assert checkpoint["current_stage"] == 0
    assert checkpoint["completed_steps"] == []
    assert checkpoint["step_outputs"] == {}


def test_skip_current_step() -> None:
    """Verify skipping step updates completed/skipped list."""
    exec_id = "exec-skip"
    create_dummy_checkpoint(exec_id, "Running")

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.SKIP_STEP,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
        metadata={"step_id": "step-2"},
    )

    success = engine.process_intervention(req)
    assert success is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert "step-2" in checkpoint["skipped_steps"]


def test_retry_current_step() -> None:
    """Verify retry clears step failures and returns execution to Running."""
    exec_id = "exec-retry"
    create_dummy_checkpoint(exec_id, "Running")

    engine = InterventionEngine()
    req = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RETRY_STEP,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
        metadata={"step_id": "step-2"},
    )

    success = engine.process_intervention(req)
    assert success is True

    checkpoint = CheckpointManager.load_checkpoint(exec_id)
    assert checkpoint is not None
    assert "step-2" not in checkpoint["failed_steps"]
    assert checkpoint["current_status"] == ExecutionStateTransition.RUNNING.value


def test_policy_enforcement_and_validation() -> None:
    """Verify authorization, state transition checks, policy compliance, and approval requirements."""
    engine = InterventionEngine()

    # 1. Non-existent execution validation
    req_bad_exec = InterventionRequest(
        execution_id="does-not-exist",
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )
    assert engine.process_intervention(req_bad_exec) is False

    # Create dummy checkpoint
    exec_id = "exec-policy-test"
    create_dummy_checkpoint(exec_id, "Running")

    # 2. EMERGENCY_STOP compliance (only allows cancel/pause)
    req_invalid_stop = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.SKIP_STEP,
        policy=InterventionPolicy.EMERGENCY_STOP,
        user_id="user-1",
        user_role="Operator",
        metadata={"step_id": "step-2"},
    )
    assert engine.process_intervention(req_invalid_stop) is False

    # 3. User role authorization (Operator/Admin/Engineer for MANUAL_ONLY)
    req_unauth_manual = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-guest",
        user_role="Guest",
    )
    assert engine.process_intervention(req_unauth_manual) is False

    # 4. ADMIN_OVERRIDE policy checks
    req_non_admin_override = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.OVERRIDE_DECISION,
        policy=InterventionPolicy.ADMIN_OVERRIDE,
        user_id="user-operator",
        user_role="Operator",
    )
    assert engine.process_intervention(req_non_admin_override) is False

    # 5. APPROVAL_REQUIRED checks
    req_missing_approval = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.APPROVAL_REQUIRED,
        user_id="user-1",
        user_role="Operator",
    )
    assert engine.process_intervention(req_missing_approval) is False

    # 6. Invalid state transitions (e.g. pausing a paused workflow)
    create_dummy_checkpoint(exec_id, "Paused")
    req_double_pause = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )
    assert engine.process_intervention(req_double_pause) is False


def test_metrics_collection() -> None:
    """Verify that intervention metrics compile counts, average timings, and success rates."""
    exec_id = "exec-metrics"
    create_dummy_checkpoint(exec_id, "Running")

    engine = InterventionEngine()

    # Trigger pause (Successful)
    req_pause = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.PAUSE,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
    )
    engine.process_intervention(req_pause)

    # Trigger resume (Successful)
    req_resume = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.RESUME,
        policy=InterventionPolicy.MANUAL_ONLY,
        user_id="user-1",
        user_role="Operator",
        metadata={"resume_latency": 1.5},
    )
    engine.process_intervention(req_resume)

    # Trigger unauthorized override (Failed)
    req_override = InterventionRequest(
        execution_id=exec_id,
        action=InterventionAction.OVERRIDE_DECISION,
        policy=InterventionPolicy.ADMIN_OVERRIDE,
        user_id="user-1",
        user_role="Operator",  # Not admin
    )
    engine.process_intervention(req_override)

    metrics = engine.get_metrics()
    assert metrics.pause_requests == 1
    assert metrics.resume_requests == 1
    assert metrics.override_requests == 1
    assert metrics.average_resume_latency == 1.5
    assert (
        metrics.intervention_success_rate == 66.66666666666666
        or metrics.intervention_success_rate == pytest.approx(66.67, 0.1)
    )
