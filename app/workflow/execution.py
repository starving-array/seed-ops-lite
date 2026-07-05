"""Core Workflow Execution Engine, Dependency Scheduler, and Checkpoint Persistence."""

import asyncio
import json
import sqlite3
import time
from abc import ABC, abstractmethod
from datetime import UTC
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.telemetry.events import EventID
from app.workflow.domain.models import WorkflowLifecycleStatus
from app.workflow.dsl.models import DSLStepType, StepDefinition, WorkflowDefinition
from app.workflow.dsl.parser import parse_reference
from app.workflow.dsl.planner import ExecutionPlan


class WorkflowStepStatus(str, Enum):
    """Execution status states of an individual workflow step."""

    PENDING = "Pending"
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"
    SKIPPED = "Skipped"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class WorkflowFailurePolicy(str, Enum):
    """Workflow execution policy to recover or fail on step exceptions."""

    FAIL_FAST = "FAIL_FAST"
    CONTINUE = "CONTINUE"
    MARK_SKIPPED = "MARK_SKIPPED"


class RecoveryPolicy(str, Enum):
    """Execution failure recovery behaviors."""

    AUTO_RESUME = "AUTO_RESUME"
    MANUAL_RESUME = "MANUAL_RESUME"
    RESTART_FROM_BEGINNING = "RESTART_FROM_BEGINNING"


class WorkflowStepResult(BaseModel):
    """The result outcome payload returned by a step executor."""

    model_config = ConfigDict(frozen=True)

    status: WorkflowStepStatus = Field(..., description="Step final execution status.")
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Outputs produced by the step."
    )
    duration: float = Field(..., description="Execution duration in seconds.")
    warnings: list[str] = Field(
        default_factory=list, description="Warnings generated during run."
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors/failures encountered."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional custom metadata."
    )


class WorkflowExecutionContext(BaseModel):
    """Context state carrying scoped variables, inputs, and outputs across execution stages."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str = Field(..., description="Reference workflow ID.")
    execution_id: str = Field(..., description="Unique run execution ID.")
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Workflow typed variables state lookup."
    )
    step_outputs: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Aggregated step outputs dictionary."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Custom context metadata tags."
    )
    runtime_statistics: dict[str, Any] = Field(
        default_factory=dict, description="Aggregated metrics."
    )
    shared_context: dict[str, Any] = Field(
        default_factory=dict, description="Shared context dict."
    )

    def with_step_output(
        self, step_id: str, outputs: dict[str, Any]
    ) -> "WorkflowExecutionContext":
        """Returns a new execution context with updated step outputs (preserves immutability)."""
        new_outputs = dict(self.step_outputs)
        new_outputs[step_id] = outputs
        return WorkflowExecutionContext(
            workflow_id=self.workflow_id,
            execution_id=self.execution_id,
            variables=self.variables,
            step_outputs=new_outputs,
            metadata=self.metadata,
            runtime_statistics=self.runtime_statistics,
            shared_context=self.shared_context,
        )


class WorkflowStepExecutor(ABC):
    """Abstract interface defining the execution protocol for workflow steps."""

    @abstractmethod
    def can_execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> bool:
        """Determines if the step is ready and can execute in the current context."""
        pass

    @abstractmethod
    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        """Executes the step logic asynchronously."""
        pass

    @abstractmethod
    def validate_inputs(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> list[str]:
        """Validates mapped input fields before execution starts."""
        pass

    @abstractmethod
    def validate_outputs(
        self, step: StepDefinition, result: WorkflowStepResult
    ) -> list[str]:
        """Validates output fields structure post-execution."""
        pass

    @abstractmethod
    def cleanup(self, step: StepDefinition) -> None:
        """Clean up resources allocated to the step post-execution."""
        pass


def resolve_value(val: Any, context: WorkflowExecutionContext) -> Any:
    """Helper to resolve expressions references (${...}) recursively."""
    if isinstance(val, dict):
        return {k: resolve_value(v, context) for k, v in val.items()}
    if isinstance(val, list):
        return [resolve_value(item, context) for item in val]
    if isinstance(val, str):
        ref = parse_reference(val)
        if ref is not None:
            if ref["type"] == "workflow":
                return context.variables.get(ref["variable"])
            if ref["type"] == "step":
                step_id = ref["step_id"]
                path = ref["path"]
                step_outs = context.step_outputs.get(step_id, {})
                current: Any = step_outs
                for p in path:
                    if isinstance(current, dict):
                        current = current.get(p)
                    else:
                        return None
                return current
    return val


class MockStepExecutor(WorkflowStepExecutor):
    """Simple mock executor simulating step execution and verifying parameter mapping."""

    def __init__(
        self, should_fail: bool = False, custom_outputs: dict[str, Any] | None = None
    ) -> None:
        self.should_fail = should_fail
        self.custom_outputs = custom_outputs or {}
        self.cleaned_up = False

    def can_execute(
        self, step: StepDefinition, _context: WorkflowExecutionContext
    ) -> bool:
        return step.enabled

    async def execute(
        self, step: StepDefinition, context: WorkflowExecutionContext
    ) -> WorkflowStepResult:
        start = time.perf_counter()
        resolved_inputs = resolve_value(step.input, context)
        duration = time.perf_counter() - start

        if self.should_fail:
            return WorkflowStepResult(
                status=WorkflowStepStatus.FAILED,
                duration=duration,
                errors=["Simulated failure"],
            )

        outputs = dict(self.custom_outputs)
        if "echo" in resolved_inputs:
            outputs["echo_out"] = resolved_inputs["echo"]

        return WorkflowStepResult(
            status=WorkflowStepStatus.COMPLETED,
            outputs=outputs,
            duration=duration,
        )

    def validate_inputs(
        self, _step: StepDefinition, _context: WorkflowExecutionContext
    ) -> list[str]:
        return []

    def validate_outputs(
        self, _step: StepDefinition, _result: WorkflowStepResult
    ) -> list[str]:
        return []

    def cleanup(self, _step: StepDefinition) -> None:
        self.cleaned_up = True


def init_checkpoint_table() -> None:
    """Creates the SQLite checkpoint storage schema dynamically."""
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_checkpoints (
                execution_id TEXT PRIMARY KEY,
                workflow_id TEXT,
                workflow_version TEXT,
                schema_version INTEGER,
                checkpoint_version TEXT,
                current_status TEXT,
                current_stage INTEGER,
                completed_steps TEXT,
                skipped_steps TEXT,
                failed_steps TEXT,
                step_outputs TEXT,
                workflow_variables TEXT,
                execution_metadata TEXT,
                created_time TEXT,
                updated_time TEXT
            )
        """
        )
        conn.commit()
    finally:
        conn.close()


class CheckpointManager:
    """Service handling checkpoint persistence, load validation, and transaction logs."""

    @staticmethod
    def save_checkpoint(
        execution_id: str,
        workflow_id: str,
        workflow_version: str,
        schema_version: int,
        checkpoint_version: str,
        current_status: str,
        current_stage: int,
        completed_steps: list[str],
        skipped_steps: list[str],
        failed_steps: list[str],
        step_outputs: dict[str, dict[str, Any]],
        workflow_variables: dict[str, Any],
        execution_metadata: dict[str, Any],
    ) -> None:
        """Saves or replaces a checkpoint state record in SQLite."""
        init_checkpoint_table()
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            from datetime import datetime

            now = datetime.now(UTC).isoformat() + "Z"

            cursor.execute(
                "SELECT created_time FROM workflow_checkpoints WHERE execution_id = ?",
                (execution_id,),
            )
            row = cursor.fetchone()
            created_time = row[0] if row else now

            cursor.execute(
                """
                INSERT OR REPLACE INTO workflow_checkpoints (
                    execution_id, workflow_id, workflow_version, schema_version, checkpoint_version,
                    current_status, current_stage, completed_steps, skipped_steps, failed_steps,
                    step_outputs, workflow_variables, execution_metadata, created_time, updated_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    execution_id,
                    workflow_id,
                    workflow_version,
                    schema_version,
                    checkpoint_version,
                    current_status,
                    current_stage,
                    json.dumps(completed_steps),
                    json.dumps(skipped_steps),
                    json.dumps(failed_steps),
                    json.dumps(step_outputs),
                    json.dumps(workflow_variables),
                    json.dumps(execution_metadata),
                    created_time,
                    now,
                ),
            )
            conn.commit()

            logger.info(
                EventID.LOG_INFO,
                "Checkpoint Created",
                details={"execution_id": execution_id, "stage": current_stage},
            )
            DomainEventDispatcher.dispatch(
                "CheckpointCreated",
                {"execution_id": execution_id, "stage": current_stage},
            )
        finally:
            conn.close()

    @staticmethod
    def load_checkpoint(execution_id: str) -> dict[str, Any] | None:
        """Loads a checkpoint state dictionary from SQLite."""
        init_checkpoint_table()
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT workflow_id, workflow_version, schema_version, checkpoint_version,
                       current_status, current_stage, completed_steps, skipped_steps, failed_steps,
                       step_outputs, workflow_variables, execution_metadata, created_time, updated_time
                FROM workflow_checkpoints WHERE execution_id = ?
            """,
                (execution_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            try:
                res = {
                    "execution_id": execution_id,
                    "workflow_id": row[0],
                    "workflow_version": row[1],
                    "schema_version": row[2],
                    "checkpoint_version": row[3],
                    "current_status": row[4],
                    "current_stage": row[5],
                    "completed_steps": json.loads(row[6]),
                    "skipped_steps": json.loads(row[7]),
                    "failed_steps": json.loads(row[8]),
                    "step_outputs": json.loads(row[9]),
                    "workflow_variables": json.loads(row[10]),
                    "execution_metadata": json.loads(row[11]),
                    "created_time": row[12],
                    "updated_time": row[13],
                }

                if not res["workflow_id"] or not res["checkpoint_version"]:
                    raise ValueError("Corrupted checkpoint metadata fields.")

                logger.info(
                    EventID.LOG_INFO,
                    "Checkpoint Restored",
                    details={"execution_id": execution_id},
                )
                DomainEventDispatcher.dispatch(
                    "CheckpointRestored", {"execution_id": execution_id}
                )
                return res
            except Exception as e:
                logger.error(
                    EventID.LOG_ERROR,
                    f"Recovery Failed: {e}",
                    details={"execution_id": execution_id},
                )
                DomainEventDispatcher.dispatch(
                    "RecoveryFailed", {"execution_id": execution_id, "error": str(e)}
                )
                raise ValueError(f"Corrupted checkpoint: {e}") from e
        finally:
            conn.close()


class DependencyScheduler:
    """Orchestrates in-process concurrency limits, parallel step scheduling, and failure recovery policies."""

    def __init__(
        self,
        plan: ExecutionPlan,
        workflow: WorkflowDefinition,
        executor_registry: dict[DSLStepType, WorkflowStepExecutor],
        failure_policy: WorkflowFailurePolicy,
        max_parallel_steps: int = 8,
        max_concurrent_ai_requests: int = 4,
    ) -> None:
        self.plan = plan
        self.workflow = workflow
        self.executor_registry = executor_registry
        self.failure_policy = failure_policy
        self.step_semaphore = asyncio.Semaphore(max_parallel_steps)
        self.ai_semaphore = asyncio.Semaphore(max_concurrent_ai_requests)
        self.active_tasks: set[str] = set()

    async def execute_stage(
        self,
        stage_num: int,
        steps: list[str],
        context: WorkflowExecutionContext,
        completed_steps: list[str],
        failed_steps: list[str],
        skipped_steps: list[str],
        errors: list[str],
    ) -> tuple[WorkflowExecutionContext, bool]:
        """Runs all steps in the stage concurrently respecting dependency constraints and failure policies."""
        logger.info(
            EventID.LOG_INFO,
            f"Stage Started: Stage {stage_num}",
            details={"stage_number": stage_num},
        )
        DomainEventDispatcher.dispatch("StageStarted", {"stage_number": stage_num})

        steps_to_run = []
        for step_id in steps:
            # Skip if already completed (loaded from checkpoint)
            if step_id in completed_steps:
                continue

            node = self.plan.nodes[step_id]
            dep_failed = any(
                dep in failed_steps or dep in skipped_steps for dep in node.dependencies
            )
            if dep_failed:
                skipped_steps.append(step_id)
                DomainEventDispatcher.dispatch("StepSkipped", {"step_id": step_id})
                continue

            step_def = next((s for s in self.workflow.steps if s.id == step_id), None)
            if step_def is None:
                continue

            if not step_def.enabled:
                skipped_steps.append(step_id)
                DomainEventDispatcher.dispatch("StepSkipped", {"step_id": step_id})
                continue

            steps_to_run.append(step_def)

        if not steps_to_run:
            logger.info(
                EventID.LOG_INFO,
                f"Stage Completed: Stage {stage_num}",
                details={"stage_number": stage_num},
            )
            DomainEventDispatcher.dispatch(
                "StageCompleted", {"stage_number": stage_num}
            )
            return context, False

        logger.info(
            EventID.LOG_INFO,
            "Concurrent Steps Started",
            details={"step_ids": [s.id for s in steps_to_run]},
        )

        async def run_single_step(
            step: StepDefinition,
        ) -> tuple[
            str, WorkflowStepStatus, dict[str, Any] | None, float | None, list[str]
        ]:
            async with self.step_semaphore:
                self.active_tasks.add(step.id)
                is_ai = step.type in (
                    DSLStepType.PROMPT,
                    DSLStepType.GENERATION,
                    DSLStepType.VALIDATION,
                )
                executor = self.executor_registry.get(step.type)

                if executor is None:
                    self.active_tasks.remove(step.id)
                    return (
                        step.id,
                        WorkflowStepStatus.FAILED,
                        None,
                        0.0,
                        [f"No executor registered for type {step.type}"],
                    )

                logger.info(
                    EventID.LOG_INFO,
                    f"Step Started: {step.id}",
                    details={"step_id": step.id},
                )
                DomainEventDispatcher.dispatch("StepStarted", {"step_id": step.id})

                start_step = time.perf_counter()
                try:
                    if is_ai:
                        async with self.ai_semaphore:
                            step_res = await executor.execute(step, context)
                    else:
                        step_res = await executor.execute(step, context)

                    duration = time.perf_counter() - start_step
                    self.active_tasks.remove(step.id)

                    if step_res.status == WorkflowStepStatus.COMPLETED:
                        logger.info(
                            EventID.LOG_INFO,
                            f"Step Completed: {step.id}",
                            details={"step_id": step.id, "duration": duration},
                        )
                        DomainEventDispatcher.dispatch(
                            "StepCompleted", {"step_id": step.id}
                        )
                        return (
                            step.id,
                            WorkflowStepStatus.COMPLETED,
                            step_res.outputs,
                            duration,
                            [],
                        )

                    logger.info(
                        EventID.LOG_INFO,
                        f"Step Failed: {step.id}",
                        details={"step_id": step.id, "errors": step_res.errors},
                    )
                    DomainEventDispatcher.dispatch(
                        "StepFailed", {"step_id": step.id, "errors": step_res.errors}
                    )
                    return (
                        step.id,
                        WorkflowStepStatus.FAILED,
                        None,
                        duration,
                        step_res.errors,
                    )
                except Exception as e:
                    duration = time.perf_counter() - start_step
                    self.active_tasks.remove(step.id)
                    logger.info(
                        EventID.LOG_INFO,
                        f"Step Failed: {step.id}",
                        details={"step_id": step.id, "error": str(e)},
                    )
                    DomainEventDispatcher.dispatch(
                        "StepFailed", {"step_id": step.id, "error": str(e)}
                    )
                    return step.id, WorkflowStepStatus.FAILED, None, duration, [str(e)]
                finally:
                    executor.cleanup(step)

        tasks = [run_single_step(s) for s in steps_to_run]
        results = await asyncio.gather(*tasks)

        logger.info(
            EventID.LOG_INFO,
            "Concurrent Steps Completed",
            details={"step_ids": [s.id for s in steps_to_run]},
        )

        stage_failed = False
        new_outputs = {}
        for step_id, status, outputs, _, step_errors in results:
            if status == WorkflowStepStatus.COMPLETED:
                completed_steps.append(step_id)
                if outputs:
                    new_outputs[step_id] = outputs
            else:
                failed_steps.append(step_id)
                errors.extend(step_errors)
                stage_failed = True

        for step_id, outputs in new_outputs.items():
            context = context.with_step_output(step_id, outputs)

        logger.info(
            EventID.LOG_INFO,
            f"Stage Completed: Stage {stage_num}",
            details={"stage_number": stage_num},
        )
        DomainEventDispatcher.dispatch("StageCompleted", {"stage_number": stage_num})

        return context, stage_failed


class WorkflowExecutionResult(BaseModel):
    """Summary outcome of a full execution run."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(..., description="Unique execution ID.")
    status: WorkflowLifecycleStatus = Field(
        ..., description="Outcome lifecycle status."
    )
    completed_steps: list[str] = Field(
        default_factory=list, description="IDs of successfully completed steps."
    )
    failed_steps: list[str] = Field(
        default_factory=list, description="IDs of failed steps."
    )
    skipped_steps: list[str] = Field(
        default_factory=list, description="IDs of skipped steps."
    )
    duration: float = Field(..., description="Total execution duration in seconds.")
    context: WorkflowExecutionContext = Field(
        ..., description="Final execution context."
    )
    errors: list[str] = Field(
        default_factory=list, description="Execution errors list."
    )


class WorkflowExecutionEngine:
    """Sequential stages scheduler executing plan stages and capturing metrics."""

    def __init__(
        self,
        plan: ExecutionPlan,
        workflow: WorkflowDefinition,
        executor_registry: dict[DSLStepType, WorkflowStepExecutor],
        failure_policy: WorkflowFailurePolicy = WorkflowFailurePolicy.FAIL_FAST,
        recovery_policy: RecoveryPolicy = RecoveryPolicy.AUTO_RESUME,
    ) -> None:
        self.plan = plan
        self.workflow = workflow
        self.executor_registry = executor_registry
        self.failure_policy = failure_policy
        self.recovery_policy = recovery_policy

    async def execute(
        self, initial_variables: dict[str, Any]
    ) -> WorkflowExecutionResult:
        start_time = time.perf_counter()

        logger.info(
            EventID.LOG_INFO,
            "Recovery Started",
            details={"workflow_id": self.plan.workflow_id},
        )
        DomainEventDispatcher.dispatch(
            "RecoveryStarted", {"workflow_id": self.plan.workflow_id}
        )

        completed_steps: list[str] = []
        failed_steps: list[str] = []
        skipped_steps: list[str] = []
        errors: list[str] = []
        is_failed = False
        start_stage = 1

        context = WorkflowExecutionContext(
            workflow_id=self.plan.workflow_id,
            execution_id=self.plan.workflow_id,
            variables=initial_variables,
        )

        # 1. Checkpoint Recovery / Resume Algorithm
        checkpoint = None
        if self.recovery_policy in (
            RecoveryPolicy.AUTO_RESUME,
            RecoveryPolicy.MANUAL_RESUME,
        ):
            checkpoint = CheckpointManager.load_checkpoint(self.plan.workflow_id)

        if checkpoint:
            completed_steps = checkpoint["completed_steps"]
            skipped_steps = checkpoint["skipped_steps"]
            failed_steps = checkpoint["failed_steps"]
            start_stage = checkpoint["current_stage"]

            # Rehydrate step outputs in execution context
            for step_id, outs in checkpoint["step_outputs"].items():
                context = context.with_step_output(step_id, outs)

            # Rehydrate variables
            context = WorkflowExecutionContext(
                workflow_id=context.workflow_id,
                execution_id=context.execution_id,
                variables=checkpoint["workflow_variables"],
                step_outputs=context.step_outputs,
                metadata=checkpoint["execution_metadata"],
            )
            logger.info(
                EventID.LOG_INFO,
                "Workflow Resumed",
                details={"workflow_id": self.plan.workflow_id},
            )
            DomainEventDispatcher.dispatch(
                "WorkflowResumed", {"workflow_id": self.plan.workflow_id}
            )
        else:
            logger.info(
                EventID.LOG_INFO,
                "Workflow Started",
                details={"workflow_id": self.plan.workflow_id},
            )
            DomainEventDispatcher.dispatch(
                "WorkflowStarted",
                {
                    "workflow_id": self.plan.workflow_id,
                    "execution_id": self.plan.workflow_id,
                },
            )
            # Save Initial Checkpoint
            CheckpointManager.save_checkpoint(
                execution_id=self.plan.workflow_id,
                workflow_id=self.plan.workflow_id,
                workflow_version="1.0.0",
                schema_version=1,
                checkpoint_version="1.0.0",
                current_status="Running",
                current_stage=0,
                completed_steps=completed_steps,
                skipped_steps=skipped_steps,
                failed_steps=failed_steps,
                step_outputs=context.step_outputs,
                workflow_variables=context.variables,
                execution_metadata=context.metadata,
            )

        max_parallel = 8
        max_ai = 4

        if hasattr(platform_settings, "WORKFLOW_MAX_PARALLEL_STEPS"):
            max_parallel = int(platform_settings.WORKFLOW_MAX_PARALLEL_STEPS)
        if hasattr(platform_settings, "WORKFLOW_MAX_CONCURRENT_AI_REQUESTS"):
            max_ai = int(platform_settings.WORKFLOW_MAX_CONCURRENT_AI_REQUESTS)

        scheduler = DependencyScheduler(
            plan=self.plan,
            workflow=self.workflow,
            executor_registry=self.executor_registry,
            failure_policy=self.failure_policy,
            max_parallel_steps=max_parallel,
            max_concurrent_ai_requests=max_ai,
        )

        for stage in self.plan.stages:
            # Skip completed stages loaded from checkpoint
            if stage.stage_number < start_stage:
                continue

            all_done = all(
                step_id in completed_steps
                or step_id in failed_steps
                or step_id in skipped_steps
                for step_id in stage.steps
            )
            if all_done:
                continue

            if is_failed and self.failure_policy == WorkflowFailurePolicy.FAIL_FAST:
                for step_id in stage.steps:
                    skipped_steps.append(step_id)
                    DomainEventDispatcher.dispatch("StepSkipped", {"step_id": step_id})
                continue

            # Before Stage Checkpoint
            CheckpointManager.save_checkpoint(
                execution_id=self.plan.workflow_id,
                workflow_id=self.plan.workflow_id,
                workflow_version="1.0.0",
                schema_version=1,
                checkpoint_version="1.0.0",
                current_status="Running",
                current_stage=stage.stage_number,
                completed_steps=completed_steps,
                skipped_steps=skipped_steps,
                failed_steps=failed_steps,
                step_outputs=context.step_outputs,
                workflow_variables=context.variables,
                execution_metadata=context.metadata,
            )

            context, stage_failed = await scheduler.execute_stage(
                stage.stage_number,
                stage.steps,
                context,
                completed_steps,
                failed_steps,
                skipped_steps,
                errors,
            )
            if stage_failed:
                is_failed = True

            # After Stage Checkpoint
            CheckpointManager.save_checkpoint(
                execution_id=self.plan.workflow_id,
                workflow_id=self.plan.workflow_id,
                workflow_version="1.0.0",
                schema_version=1,
                checkpoint_version="1.0.0",
                current_status="Failed" if is_failed else "Running",
                current_stage=stage.stage_number,
                completed_steps=completed_steps,
                skipped_steps=skipped_steps,
                failed_steps=failed_steps,
                step_outputs=context.step_outputs,
                workflow_variables=context.variables,
                execution_metadata=context.metadata,
            )

        duration = time.perf_counter() - start_time
        status = (
            WorkflowLifecycleStatus.FAILED
            if is_failed
            else WorkflowLifecycleStatus.COMPLETED
        )

        # Final Checkpoint on completion / failure
        CheckpointManager.save_checkpoint(
            execution_id=self.plan.workflow_id,
            workflow_id=self.plan.workflow_id,
            workflow_version="1.0.0",
            schema_version=1,
            checkpoint_version="1.0.0",
            current_status=status.value,
            current_stage=len(self.plan.stages),
            completed_steps=completed_steps,
            skipped_steps=skipped_steps,
            failed_steps=failed_steps,
            step_outputs=context.step_outputs,
            workflow_variables=context.variables,
            execution_metadata=context.metadata,
        )

        if status == WorkflowLifecycleStatus.COMPLETED:
            logger.info(
                EventID.LOG_INFO,
                "Recovery Completed",
                details={"workflow_id": self.plan.workflow_id, "duration": duration},
            )
            DomainEventDispatcher.dispatch(
                "WorkflowCompleted", {"workflow_id": self.plan.workflow_id}
            )
            DomainEventDispatcher.dispatch(
                "RecoveryCompleted", {"workflow_id": self.plan.workflow_id}
            )
        else:
            logger.info(
                EventID.LOG_INFO,
                "Recovery Failed",
                details={
                    "workflow_id": self.plan.workflow_id,
                    "duration": duration,
                    "errors": errors,
                },
            )
            DomainEventDispatcher.dispatch(
                "WorkflowFailed",
                {"workflow_id": self.plan.workflow_id, "errors": errors},
            )
            DomainEventDispatcher.dispatch(
                "RecoveryFailed",
                {"workflow_id": self.plan.workflow_id, "errors": errors},
            )

        return WorkflowExecutionResult(
            execution_id=self.plan.workflow_id,
            status=status,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
            skipped_steps=skipped_steps,
            duration=duration,
            context=context,
            errors=errors,
        )
