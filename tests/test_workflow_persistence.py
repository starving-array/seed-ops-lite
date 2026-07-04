"""Unit tests for Workflow persistence, versioning, and audits."""

import sqlite3

import pytest

from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
    WorkflowDefinition,
)
from app.workflow.persistence import (
    SQLiteWorkflowRepository,
    WorkflowDiffEngine,
)


@pytest.fixture(autouse=True)
def clean_workflow_tables() -> None:
    """Ensure database tables are fresh for each run."""
    from app.platform.providers.sqlite_db import sqlite_db_manager

    # Initial trigger to make tables
    SQLiteWorkflowRepository()
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_definitions")
        cursor.execute("DELETE FROM workflow_audit_trail")
        conn.commit()
    finally:
        conn.close()


def test_repository_save_and_retrieve() -> None:
    """Verify CRUD and basic retrieval flows of definitions."""
    repo = SQLiteWorkflowRepository()

    step = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    workflow = WorkflowDefinition(
        id="wf-pers-1",
        workflow_version="1.0.0",
        name="Persistence test workflow",
        steps=[step],
    )

    repo.save(workflow, change_summary="First save draft", actor="developer-Alice")

    # Load version
    loaded = repo.get("wf-pers-1", "1.0.0")
    assert loaded is not None
    assert loaded.name == "Persistence test workflow"
    assert len(loaded.steps) == 1


def test_repository_version_immutability() -> None:
    """Verify that saving the exact same version string twice raises an error."""
    repo = SQLiteWorkflowRepository()

    step = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    workflow = WorkflowDefinition(
        id="wf-immutable-test",
        workflow_version="1.0.0",
        name="Immutable check",
        steps=[step],
    )

    repo.save(workflow, change_summary="First draft save", actor="Alice")

    with pytest.raises(ValueError, match="is immutable and cannot be overwritten"):
        repo.save(workflow, change_summary="Accidental overwrite", actor="Bob")


def test_repository_version_increment() -> None:
    """Verify version increments and latest version searches."""
    repo = SQLiteWorkflowRepository()

    step = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    v1 = WorkflowDefinition(
        id="wf-v-test",
        workflow_version="1.0.0",
        name="Initial draft",
        steps=[step],
    )
    v2 = WorkflowDefinition(
        id="wf-v-test",
        workflow_version="1.1.0",
        name="Incremental change",
        steps=[step],
    )

    repo.save(v1, change_summary="V1 draft", actor="Alice")
    repo.save(v2, change_summary="V2 draft", actor="Bob")

    latest = repo.get_latest("wf-v-test")
    assert latest is not None
    assert latest.workflow_version == "1.1.0"
    assert latest.name == "Incremental change"


def test_repository_soft_delete_and_restore() -> None:
    """Verify soft deleting hide definitions and restores them correctly."""
    repo = SQLiteWorkflowRepository()

    step = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    workflow = WorkflowDefinition(
        id="wf-del-restore",
        workflow_version="1.0.0",
        name="Trash check",
        steps=[step],
    )

    repo.save(workflow, change_summary="V1", actor="Alice")

    # Verify visible
    assert repo.get("wf-del-restore", "1.0.0") is not None

    # Soft delete
    repo.soft_delete("wf-del-restore", actor="Alice")
    assert repo.get("wf-del-restore", "1.0.0") is None

    # Restore
    repo.restore("wf-del-restore", actor="Alice")
    assert repo.get("wf-del-restore", "1.0.0") is not None


def test_workflow_diff_engine() -> None:
    """Verify structural comparison and variable diffs reporting."""
    s1 = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    s2 = StepDefinition(id="step-2", name="Step 2", type=DSLStepType.GENERATION)

    v1 = WorkflowDefinition(
        id="wf-diff",
        workflow_version="1.0.0",
        name="Base version",
        steps=[s1],
    )
    # V2 removes step 1, adds step 2
    v2 = WorkflowDefinition(
        id="wf-diff",
        workflow_version="1.1.0",
        name="Modified name",
        steps=[s2],
    )

    diff = WorkflowDiffEngine.diff(v1, v2)
    assert "step-1" in diff.step_changes.removed
    assert "step-2" in diff.step_changes.added
    assert "name" in diff.metadata_changes


def test_audit_trail_logging() -> None:
    """Verify event tracking history logs."""
    repo = SQLiteWorkflowRepository()
    step = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    workflow = WorkflowDefinition(
        id="wf-audit-trail",
        workflow_version="1.0.0",
        name="Audit test workflow",
        steps=[step],
    )

    repo.save(workflow, change_summary="Initial commit", actor="Alice")
    repo.soft_delete("wf-audit-trail", actor="Bob")

    trail = repo.get_audit_trail("wf-audit-trail")
    assert len(trail) == 2
    assert trail[0].event_type == "WorkflowDeleted"
    assert trail[0].actor == "Bob"
    assert trail[1].event_type == "WorkflowCreated"
    assert trail[1].actor == "Alice"
