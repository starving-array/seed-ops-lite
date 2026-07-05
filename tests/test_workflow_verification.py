"""Verification script confirming the complete End-to-End Workflow lifecycle."""

import sqlite3

from app.workflow.dsl.models import DSLStepType, StepDefinition, WorkflowDefinition
from app.workflow.persistence import SQLiteWorkflowRepository
from app.workflow.service import WorkflowService


def test_complete_e2e_verification_lifecycle() -> None:
    """End-to-End verification test tracking expected and observed behavior across all systems."""
    # 1. Initialize repository and clean old records
    repo = SQLiteWorkflowRepository()
    service = WorkflowService(repo)

    from app.platform.providers.sqlite_db import sqlite_db_manager

    conn = sqlite3.connect(sqlite_db_manager.db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_definitions")
        cursor.execute("DELETE FROM workflow_audit_trail")
        cursor.execute("DELETE FROM workflow_checkpoints")
        conn.commit()
    finally:
        conn.close()

    # Stage 1: Create Workflow
    step1 = StepDefinition(
        id="step-1",
        name="Prompt Step",
        type=DSLStepType.PROMPT,
        input={"prompt": "Translate: Hello"},
    )
    step2 = StepDefinition(
        id="step-2", name="Export Step", type=DSLStepType.EXPORT, depends_on=["step-1"]
    )
    wf = WorkflowDefinition(
        id="wf-verify-e2e",
        workflow_version="1.0.0",
        name="Verification Workflow",
        steps=[step1, step2],
    )
    service.create_workflow(wf, change_summary="Verification setup", actor="verifier")

    saved_wf = service.get_workflow("wf-verify-e2e", "1.0.0")
    assert saved_wf is not None
    assert saved_wf.name == "Verification Workflow"

    # Stage 2: Validate
    val_res = service.validate_workflow(wf)
    assert val_res.valid is True

    # Stage 3: Publish
    service.repo.publish("wf-verify-e2e", "1.0.0", actor="verifier")
    published_wf = service.repo.get("wf-verify-e2e", "1.0.0")
    assert published_wf is not None

    # Stage 4: Plan
    plan = service.plan_workflow(wf)
    assert len(plan.stages) == 2

    # Stage 5: Auditing Check
    audit_trail = service.repo.get_audit_trail("wf-verify-e2e")
    event_types = [entry.event_type for entry in audit_trail]
    assert "WorkflowCreated" in event_types
    assert "WorkflowPublished" in event_types
