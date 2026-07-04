"""End-to-End Workflow Platform Integration tests using FastAPI TestClient."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.workflow.persistence import SQLiteWorkflowRepository


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Fixture to truncate workflow definition, audit, and checkpoint tables before run."""
    from app.platform.providers.sqlite_db import sqlite_db_manager

    SQLiteWorkflowRepository()
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_definitions")
        cursor.execute("DELETE FROM workflow_audit_trail")
        cursor.execute("DELETE FROM workflow_checkpoints")
        conn.commit()
    finally:
        conn.close()


def test_workflow_platform_e2e() -> None:
    """Verify E2E creation, validation, publishing, and export REST API calls."""
    client = TestClient(app)

    payload = {
        "id": "wf-platform-e2e",
        "schema_version": 1,
        "workflow_version": "1.0.0",
        "name": "E2E Platform Pipeline",
        "steps": [
            {
                "id": "step-A",
                "name": "First Step",
                "type": "Prompt",
                "input": {"prompt": "Start pipeline"},
            }
        ],
    }

    # 1. Create Workflow via REST
    resp_create = client.post("/workflows/workflows", json=payload)
    assert resp_create.status_code == 201
    assert resp_create.json()["status"] == "success"

    # 2. Get latest workflow definition
    resp_get = client.get("/workflows/workflows/wf-platform-e2e")
    assert resp_get.status_code == 200
    assert resp_get.json()["name"] == "E2E Platform Pipeline"

    # 3. Validate
    resp_val = client.post(
        "/workflows/workflows/wf-platform-e2e/validate?version=1.0.0"
    )
    assert resp_val.status_code == 200
    assert resp_val.json()["valid"] is True

    # 4. Publish
    resp_pub = client.post("/workflows/workflows/wf-platform-e2e/publish?version=1.0.0")
    assert resp_pub.status_code == 200
    assert "published" in resp_pub.json()["message"]

    # 5. Export
    resp_exp = client.get("/workflows/workflows/wf-platform-e2e/export")
    assert resp_exp.status_code == 200
    assert resp_exp.json()["id"] == "wf-platform-e2e"

    # 6. Import
    payload_import = dict(payload)
    payload_import["id"] = "wf-platform-import"
    resp_imp = client.post("/workflows/workflows/import", json=payload_import)
    assert resp_imp.status_code == 200
    assert "imported" in resp_imp.json()["message"]


@pytest.mark.asyncio
async def test_workflow_execution_and_resume_endpoints() -> None:
    """Verify execution lifecycle, checkpoint, and cancellation endpoints."""
    # Pre-populate workflow version to run
    repo = SQLiteWorkflowRepository()
    from app.workflow.dsl.models import DSLStepType, StepDefinition, WorkflowDefinition

    wf = WorkflowDefinition(
        id="wf-exec-platform",
        workflow_version="1.0.0",
        name="Platform Exec Pipeline",
        steps=[
            StepDefinition(
                id="step-1",
                name="Step 1",
                type=DSLStepType.PROMPT,
                input={"prompt": "test"},
            )
        ],
    )
    repo.save(wf, change_summary="Ready for run", actor="test-runner")

    client = TestClient(app)

    # Execute
    resp_exec = client.post(
        "/workflows/workflows/wf-exec-platform/execute",
        json={"version": "1.0.0", "variables": {}},
    )
    assert resp_exec.status_code == 200
    assert resp_exec.json()["status"] == "Completed"

    # Get status from checkpoints
    resp_status = client.get(f"/workflows/executions/{wf.id}")
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] == "Completed"

    # Cancel execution run
    resp_cancel = client.post(f"/workflows/executions/{wf.id}/cancel")
    assert resp_cancel.status_code == 200
    assert "cancelled" in resp_cancel.json()["message"]
