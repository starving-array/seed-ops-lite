"""WorkflowService façade coordinating validation, planning, execution, and persistence."""

from typing import Any

from pydantic import BaseModel

from app.platform.providers.sqlite_db import sqlite_db_manager
from app.workflow.domain.models import WorkflowLifecycleStatus
from app.workflow.dsl.models import DSLStepType, WorkflowDefinition
from app.workflow.dsl.planner import ExecutionPlan, WorkflowExecutionPlanner
from app.workflow.dsl.validator_engine import ValidationResult, WorkflowValidator
from app.workflow.execution import (
    CheckpointManager,
    MockStepExecutor,
    RecoveryPolicy,
    WorkflowExecutionEngine,
    WorkflowExecutionResult,
    WorkflowStepExecutor,
)
from app.workflow.persistence import (
    SQLiteWorkflowRepository,
    WorkflowDiff,
    WorkflowDiffEngine,
)


class ExecutionStatusSummary(BaseModel):
    """API model summarizing an execution's run state."""

    execution_id: str
    status: str
    current_stage: int
    completed_steps: list[str]
    skipped_steps: list[str]
    failed_steps: list[str]
    duration: float
    checkpoint_count: int


class PlatformSummary(BaseModel):
    """Platform-wide summary metrics for dashboards."""

    total_workflows: int
    published_versions: int
    archived_workflows: int
    active_executions: int
    success_rate: float
    average_duration: float


class WorkflowService:
    """Facade orchestrating all Workflow engine and persistence subsystems."""

    def __init__(self, repository: SQLiteWorkflowRepository | None = None) -> None:
        self.repo = repository or SQLiteWorkflowRepository()

    def create_workflow(
        self, workflow: WorkflowDefinition, change_summary: str, actor: str
    ) -> None:
        self.repo.save(workflow, change_summary, actor)

    def get_workflow(self, workflow_id: str, version: str) -> WorkflowDefinition | None:
        return self.repo.get(workflow_id, version)

    def get_latest_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        return self.repo.get_latest(workflow_id)

    def list_workflows(self, include_deleted: bool = False) -> list[WorkflowDefinition]:
        return self.repo.list_workflows(include_deleted)

    def soft_delete_workflow(self, workflow_id: str, actor: str) -> None:
        self.repo.soft_delete(workflow_id, actor)

    def restore_workflow(self, workflow_id: str, actor: str) -> None:
        self.repo.restore(workflow_id, actor)

    def validate_workflow(self, workflow: WorkflowDefinition) -> ValidationResult:
        return WorkflowValidator.validate(workflow)

    def plan_workflow(self, workflow: WorkflowDefinition) -> ExecutionPlan:
        return WorkflowExecutionPlanner.plan(workflow)

    async def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        initial_variables: dict[str, Any],
        recovery_policy: RecoveryPolicy = RecoveryPolicy.AUTO_RESUME,
    ) -> WorkflowExecutionResult:
        plan = self.plan_workflow(workflow)

        # Simple default registry using Mock executors for the standard step types
        mock_exec = MockStepExecutor()
        registry: dict[DSLStepType, WorkflowStepExecutor] = {
            DSLStepType.PROMPT: mock_exec,
            DSLStepType.GENERATION: mock_exec,
            DSLStepType.VALIDATION: mock_exec,
            DSLStepType.TRANSFORM: mock_exec,
            DSLStepType.EXPORT: mock_exec,
            DSLStepType.HUMAN_APPROVAL: mock_exec,
            DSLStepType.DELAY: mock_exec,
            DSLStepType.CONDITION: mock_exec,
            DSLStepType.LOOP: mock_exec,
            DSLStepType.MERGE: mock_exec,
            DSLStepType.WEBHOOK: mock_exec,
        }

        engine = WorkflowExecutionEngine(
            plan=plan,
            workflow=workflow,
            executor_registry=registry,
            recovery_policy=recovery_policy,
        )
        return await engine.execute(initial_variables)

    def get_execution_status(self, execution_id: str) -> ExecutionStatusSummary | None:
        checkpoint = CheckpointManager.load_checkpoint(execution_id)
        if not checkpoint:
            return None

        # Fetch count from database
        import sqlite3

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        checkpoint_count = 0
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM workflow_checkpoints WHERE execution_id = ?",
                (execution_id,),
            )
            row = cursor.fetchone()
            if row:
                checkpoint_count = row[0]
        finally:
            conn.close()

        # Simple duration estimation from timestamps
        from datetime import datetime

        try:
            created = datetime.fromisoformat(checkpoint["created_time"].rstrip("Z"))
            updated = datetime.fromisoformat(checkpoint["updated_time"].rstrip("Z"))
            duration = (updated - created).total_seconds()
        except Exception:
            duration = 0.0

        return ExecutionStatusSummary(
            execution_id=execution_id,
            status=checkpoint["current_status"],
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            duration=duration,
            checkpoint_count=checkpoint_count,
        )

    def diff_workflows(
        self, v1: WorkflowDefinition, v2: WorkflowDefinition
    ) -> WorkflowDiff:
        return WorkflowDiffEngine.diff(v1, v2)

    def get_platform_summary(self) -> PlatformSummary:
        workflows = self.list_workflows()
        total_wfs = len(workflows)
        published_wfs = sum(1 for w in workflows if len(w.steps) > 0)

        # Connect to SQLite to count executions and compute average duration
        import sqlite3

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        success_count = 0
        failed_count = 0
        total_runs = 0
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT current_status FROM workflow_checkpoints")
            rows = cursor.fetchall()
            for r in rows:
                status = r[0]
                if status == WorkflowLifecycleStatus.COMPLETED.value:
                    success_count += 1
                elif status == WorkflowLifecycleStatus.FAILED.value:
                    failed_count += 1
                total_runs += 1
        finally:
            conn.close()

        success_rate = (success_count / total_runs * 100.0) if total_runs > 0 else 100.0

        return PlatformSummary(
            total_workflows=total_wfs,
            published_versions=published_wfs,
            archived_workflows=0,
            active_executions=total_runs - (success_count + failed_count),
            success_rate=round(success_rate, 2),
            average_duration=5.0,  # Mock average execution duration
        )
