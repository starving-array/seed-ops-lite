"""FastAPI routing endpoints for workflow and executions API resources."""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.workflow.dsl.models import WorkflowDefinition
from app.workflow.execution import RecoveryPolicy
from app.workflow.service import WorkflowService

router = APIRouter()
service = WorkflowService()


@router.get("/workflows", response_model=list[dict[str, Any]])
def list_workflows(include_deleted: bool = False) -> list[dict[str, Any]]:
    """List active workflows definitions."""
    wfs = service.list_workflows(include_deleted)
    return [w.model_dump() for w in wfs]


@router.post("/workflows", status_code=201)
def create_workflow(workflow: WorkflowDefinition) -> dict[str, str]:
    """Create a new workflow definition."""
    try:
        service.create_workflow(
            workflow, change_summary="Created workflow definition.", actor="API-user"
        )
        return {
            "status": "success",
            "message": f"Workflow {workflow.id} version {workflow.workflow_version} saved.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/workflows/{workflow_id}", response_model=dict[str, Any])
def get_workflow(workflow_id: str, version: str | None = None) -> dict[str, Any]:
    """Retrieve specific workflow definition version."""
    if version:
        wf = service.get_workflow(workflow_id, version)
    else:
        wf = service.get_latest_workflow(workflow_id)

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.model_dump()


@router.put("/workflows/{workflow_id}", response_model=dict[str, str])
def update_workflow(workflow_id: str, workflow: WorkflowDefinition) -> dict[str, str]:
    """Update (increment version of) a workflow definition."""
    if workflow.id != workflow_id:
        raise HTTPException(
            status_code=400, detail="Path workflow ID and body ID mismatch."
        )
    try:
        service.create_workflow(
            workflow, change_summary="Incremental update via PUT.", actor="API-user"
        )
        return {
            "status": "success",
            "message": f"Workflow {workflow.id} version {workflow.workflow_version} saved.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/workflows/{workflow_id}")
def delete_workflow(workflow_id: str) -> dict[str, str]:
    """Soft delete a workflow definition."""
    service.soft_delete_workflow(workflow_id, actor="API-user")
    return {"status": "success", "message": f"Workflow {workflow_id} soft deleted."}


@router.post("/workflows/{workflow_id}/publish")
def publish_workflow(workflow_id: str, version: str) -> dict[str, str]:
    """Publishes a workflow definition version."""
    wf = service.get_workflow(workflow_id, version)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    service.repo.publish(workflow_id, version, actor="API-user")
    return {
        "status": "success",
        "message": f"Workflow {workflow_id} version {version} published.",
    }


@router.post("/workflows/{workflow_id}/validate")
def validate_workflow(workflow_id: str, version: str) -> dict[str, Any]:
    """Audits and validates the workflow graph structures."""
    wf = service.get_workflow(workflow_id, version)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    res = service.validate_workflow(wf)
    return res.model_dump()


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Triggers execution run for a workflow definition."""
    version = payload.get("version", "1.0.0")
    wf = service.get_workflow(workflow_id, version)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow version not found")

    variables = payload.get("variables", {})
    policy_str = payload.get("recovery_policy", "AUTO_RESUME")
    policy = RecoveryPolicy(policy_str)

    try:
        res = await service.execute_workflow(wf, variables, policy)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str) -> dict[str, Any]:
    """Retrieve run execution metadata and active stage status."""
    res = service.get_execution_status(execution_id)
    if not res:
        raise HTTPException(status_code=404, detail="Execution not found")
    return res.model_dump()


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Resume execution from checkpoint."""
    # Find workflow details from checkpoint
    status = service.get_execution_status(execution_id)
    if not status:
        raise HTTPException(status_code=404, detail="Execution checkpoint not found")

    wf_id = (
        execution_id  # Assuming execution id maps to workflow id in sequential setup
    )
    version = payload.get("version", "1.0.0")
    wf = service.get_workflow(wf_id, version)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    variables = payload.get("variables", {})
    try:
        res = await service.execute_workflow(wf, variables, RecoveryPolicy.AUTO_RESUME)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/executions/{execution_id}/cancel")
def cancel_execution(execution_id: str) -> dict[str, str]:
    """Aborts/cancels a running execution."""
    # Mock cancellation save checkpoint
    from app.workflow.execution import CheckpointManager

    CheckpointManager.save_checkpoint(
        execution_id=execution_id,
        workflow_id=execution_id,
        workflow_version="1.0.0",
        schema_version=1,
        checkpoint_version="1.0.0",
        current_status="Cancelled",
        current_stage=0,
        completed_steps=[],
        skipped_steps=[],
        failed_steps=[],
        step_outputs={},
        workflow_variables={},
        execution_metadata={},
    )
    return {"status": "success", "message": f"Execution {execution_id} cancelled."}


@router.post("/workflows/import")
def import_workflow(payload: dict[str, Any]) -> dict[str, str]:
    """Imports workflow DSL and runs schema validations before persistence."""
    try:
        wf = WorkflowDefinition.model_validate(payload)
        service.create_workflow(
            wf, change_summary="Imported workflow.", actor="API-user"
        )
        return {
            "status": "success",
            "message": f"Workflow {wf.id} imported successfully.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/workflows/{workflow_id}/export")
def export_workflow(workflow_id: str, version: str | None = None) -> dict[str, Any]:
    """Export a workflow definition JSON layout."""
    if version:
        wf = service.get_workflow(workflow_id, version)
    else:
        wf = service.get_latest_workflow(workflow_id)

    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.model_dump()
