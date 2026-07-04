"""Unit tests for Checkpointing, Resume & Recovery policies."""

import sqlite3

import pytest

from app.workflow.domain.models import WorkflowLifecycleStatus
from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
    WorkflowDefinition,
    WorkflowExecutionPlanner,
)
from app.workflow.execution import (
    CheckpointManager,
    MockStepExecutor,
    RecoveryPolicy,
    WorkflowExecutionEngine,
)


@pytest.fixture(autouse=True)
def clean_checkpoints_table() -> None:
    """Fixture to ensure checkpoints table is truncated between tests."""
    from app.platform.providers.sqlite_db import sqlite_db_manager

    CheckpointManager.save_checkpoint(
        execution_id="dummy",
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
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_checkpoints")
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_checkpoint_save_and_load() -> None:
    """Verify that CheckpointManager writes and reads checkpoints accurately from SQLite."""
    CheckpointManager.save_checkpoint(
        execution_id="exec-101",
        workflow_id="wf-abc",
        workflow_version="2.0.0",
        schema_version=1,
        checkpoint_version="1.0.0",
        current_status="Running",
        current_stage=2,
        completed_steps=["step-1"],
        skipped_steps=[],
        failed_steps=[],
        step_outputs={"step-1": {"result": "success"}},
        workflow_variables={"user": "Alice"},
        execution_metadata={"host": "localhost"},
    )

    checkpoint = CheckpointManager.load_checkpoint("exec-101")
    assert checkpoint is not None
    assert checkpoint["workflow_id"] == "wf-abc"
    assert checkpoint["workflow_version"] == "2.0.0"
    assert checkpoint["current_stage"] == 2
    assert checkpoint["completed_steps"] == ["step-1"]
    assert checkpoint["step_outputs"]["step-1"]["result"] == "success"
    assert checkpoint["workflow_variables"]["user"] == "Alice"


@pytest.mark.asyncio
async def test_checkpoint_corruption() -> None:
    """Verify corrupted checkpoint checks detect malformed schemas."""
    # Write invalid data directly to table to bypass save validations
    from app.platform.providers.sqlite_db import sqlite_db_manager

    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO workflow_checkpoints (execution_id, workflow_id, checkpoint_version)
            VALUES (?, ?, ?)
        """,
            ("exec-bad", None, None),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(ValueError, match="Corrupted checkpoint"):
        CheckpointManager.load_checkpoint("exec-bad")


@pytest.mark.asyncio
async def test_workflow_resume_flow() -> None:
    """Verify that execution skips already completed steps when resuming from a checkpoint."""
    step1 = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-2", name="Step 2", type=DSLStepType.GENERATION, depends_on=["step-1"]
    )
    workflow = WorkflowDefinition(
        id="wf-resume-test",
        name="Resume Test Pipeline",
        steps=[step1, step2],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)

    # Pre-populate checkpoint indicating step-1 is already COMPLETED
    CheckpointManager.save_checkpoint(
        execution_id=plan.workflow_id,
        workflow_id=plan.workflow_id,
        workflow_version="1.0.0",
        schema_version=1,
        checkpoint_version="1.0.0",
        current_status="Running",
        current_stage=1,
        completed_steps=["step-1"],
        skipped_steps=[],
        failed_steps=[],
        step_outputs={"step-1": {"echo_out": "recovered_value"}},
        workflow_variables={},
        execution_metadata={},
    )

    # Use executors
    exec1 = MockStepExecutor()
    exec2 = MockStepExecutor(custom_outputs={"res2": "hello"})
    registry = {
        DSLStepType.PROMPT: exec1,
        DSLStepType.GENERATION: exec2,
    }

    # Execute with AUTO_RESUME policy
    engine = WorkflowExecutionEngine(
        plan=plan,
        workflow=workflow,
        executor_registry=registry,
        recovery_policy=RecoveryPolicy.AUTO_RESUME,
    )

    result = await engine.execute(initial_variables={})

    assert result.status == WorkflowLifecycleStatus.COMPLETED
    assert result.completed_steps == ["step-1", "step-2"]
    assert result.context.step_outputs["step-1"]["echo_out"] == "recovered_value"
    assert result.context.step_outputs["step-2"]["res2"] == "hello"

    # Step 1 should have been skipped in the execution run since it was loaded from the checkpoint
    # MockStepExecutor's execution count remains 0 for step 1
    assert exec1.cleaned_up is False
    assert exec2.cleaned_up is True
