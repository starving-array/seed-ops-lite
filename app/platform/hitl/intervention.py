"""Human-in-the-Loop (HITL) Intervention Engine and Execution Control."""

import contextlib
import json
import sqlite3
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.telemetry.events import EventID

# Reuse CheckpointManager
from app.workflow.execution import CheckpointManager


# Enums
class InterventionPolicy(str, Enum):
    """Policies dictating allowed human intervention actions and workflows."""

    MANUAL_ONLY = "MANUAL_ONLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    AUTO_RESUME = "AUTO_RESUME"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class InterventionAction(str, Enum):
    """Supported human intervention actions."""

    PAUSE = "Pause Execution"
    RESUME = "Resume Execution"
    CANCEL = "Cancel Execution"
    RESTART_CHECKPOINT = "Restart From Checkpoint"
    RESTART_BEGINNING = "Restart From Beginning"
    SKIP_STEP = "Skip Current Step"
    RETRY_STEP = "Retry Current Step"
    OVERRIDE_DECISION = "Override Decision"
    CONTINUE = "Continue Execution"


class ExecutionStateTransition(str, Enum):
    """States specifically tracked by the intervention engine."""

    RUNNING = "Running"
    PAUSED = "Paused"
    RESUMED = "Resumed"
    CANCELLED = "Cancelled"
    RESTARTED = "Restarted"


# Models
class InterventionRequest(BaseModel):
    """Pydantic model representing an intervention request."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(..., description="Target execution ID.")
    action: InterventionAction = Field(..., description="Action to perform.")
    policy: InterventionPolicy = Field(..., description="Compliance policy applied.")
    user_id: str = Field(..., description="Initiating user's ID.")
    user_role: str = Field(..., description="Initiating user's role.")
    approval_id: str | None = Field(
        default=None, description="Linked approval request ID."
    )
    checkpoint_id: str | None = Field(
        default=None, description="Checkpoint ID if restarting."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata tags mapping details."
    )


class InterventionHistoryEntry(BaseModel):
    """Pydantic model representing a completed intervention event log."""

    model_config = ConfigDict(frozen=True)

    entry_id: str = Field(..., description="Unique entry ID.")
    execution_id: str = Field(..., description="Target execution ID.")
    action: str = Field(..., description="Performed action.")
    policy: str = Field(..., description="Enforced policy.")
    state_before: str = Field(..., description="State before intervention.")
    state_after: str = Field(..., description="State after intervention.")
    user_id: str = Field(..., description="User ID.")
    timestamp: float = Field(..., description="Epoch timestamp.")
    success: bool = Field(..., description="Whether action completed successfully.")
    comments: str | None = Field(default=None)


class InterventionStatistics(BaseModel):
    """Aggregated metrics for the HITL Intervention Engine."""

    pause_requests: int = 0
    resume_requests: int = 0
    cancel_requests: int = 0
    restart_requests: int = 0
    override_requests: int = 0
    average_pause_duration: float = 0.0
    average_resume_latency: float = 0.0
    intervention_success_rate: float = 0.0


# Initialize db table for interventions
def init_interventions_table() -> None:
    """Ensure the workflow_interventions SQLite table exists."""
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_interventions (
                entry_id TEXT PRIMARY KEY,
                execution_id TEXT,
                action TEXT,
                policy TEXT,
                state_before TEXT,
                state_after TEXT,
                user_id TEXT,
                timestamp REAL,
                success INTEGER,
                comments TEXT,
                metadata TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class PauseManager:
    """Manages pause operations on execution sessions."""

    def __init__(self) -> None:
        pass

    def pause_execution(self, execution_id: str, checkpoint: dict[str, Any]) -> None:
        """Pause a running execution by updating its persistent state."""
        # Update checkpoint status to Paused
        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.PAUSED.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            step_outputs=checkpoint["step_outputs"],
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata={
                **checkpoint["execution_metadata"],
                "paused_at": time.time(),
            },
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution paused: {execution_id}",
            component="PauseManager",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionPaused", {"execution_id": execution_id}
        )


class ResumeManager:
    """Manages resume operations on paused execution sessions."""

    def __init__(self) -> None:
        pass

    def resume_execution(self, execution_id: str, checkpoint: dict[str, Any]) -> None:
        """Resume a paused execution by restoring state transitions to Resumed then Running."""
        paused_at = checkpoint["execution_metadata"].get("paused_at", time.time())
        resume_latency = time.time() - paused_at

        # First, transient state Resumed
        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RESUMED.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            step_outputs=checkpoint["step_outputs"],
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata={
                **checkpoint["execution_metadata"],
                "resume_latency": resume_latency,
                "resumed_at": time.time(),
            },
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution resumed: {execution_id}",
            component="ResumeManager",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionResumed",
            {"execution_id": execution_id, "resume_latency": resume_latency},
        )

        # Transition back to Running
        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RUNNING.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            step_outputs=checkpoint["step_outputs"],
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata=checkpoint["execution_metadata"],
        )


class ExecutionController:
    """Controls advanced execution options including cancellation, skipping, and retrying."""

    def __init__(self) -> None:
        pass

    def cancel_execution(self, execution_id: str, checkpoint: dict[str, Any]) -> None:
        """Cancel the active execution."""
        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.CANCELLED.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            step_outputs=checkpoint["step_outputs"],
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata=checkpoint["execution_metadata"],
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution cancelled: {execution_id}",
            component="ExecutionController",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionCancelled", {"execution_id": execution_id}
        )

    def restart_from_checkpoint(
        self, execution_id: str, checkpoint: dict[str, Any]
    ) -> None:
        """Restart execution stage/progress from last saved checkpoint."""
        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RESTARTED.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            step_outputs=checkpoint["step_outputs"],
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata=checkpoint["execution_metadata"],
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution restarted from checkpoint: {execution_id}",
            component="ExecutionController",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionRestartedFromCheckpoint", {"execution_id": execution_id}
        )

    def restart_from_beginning(
        self, execution_id: str, checkpoint: dict[str, Any]
    ) -> None:
        """Restart execution from the first stage, clearing progress and step outputs."""
        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RUNNING.value,
            current_stage=0,
            completed_steps=[],
            skipped_steps=[],
            failed_steps=[],
            step_outputs={},
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata={},
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution restarted from beginning: {execution_id}",
            component="ExecutionController",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionRestartedFromBeginning", {"execution_id": execution_id}
        )

    def skip_current_step(
        self, execution_id: str, checkpoint: dict[str, Any], step_id: str
    ) -> None:
        """Skip the specified step in the execution flow."""
        completed_steps = list(checkpoint["completed_steps"])
        skipped_steps = list(checkpoint["skipped_steps"])
        if step_id not in skipped_steps and step_id not in completed_steps:
            skipped_steps.append(step_id)

        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RUNNING.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=completed_steps,
            skipped_steps=skipped_steps,
            failed_steps=checkpoint["failed_steps"],
            step_outputs={**checkpoint["step_outputs"], step_id: {"skipped": True}},
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata=checkpoint["execution_metadata"],
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution step skipped: {step_id} in {execution_id}",
            component="ExecutionController",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionStepSkipped", {"execution_id": execution_id, "step_id": step_id}
        )

    def retry_current_step(
        self, execution_id: str, checkpoint: dict[str, Any], step_id: str
    ) -> None:
        """Clear failures/outputs for step_id and restore state to Running to trigger a retry."""
        failed_steps = [s for s in checkpoint["failed_steps"] if s != step_id]
        completed_steps = [s for s in checkpoint["completed_steps"] if s != step_id]

        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RUNNING.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=completed_steps,
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=failed_steps,
            step_outputs={
                k: v for k, v in checkpoint["step_outputs"].items() if k != step_id
            },
            workflow_variables=checkpoint["workflow_variables"],
            execution_metadata=checkpoint["execution_metadata"],
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution step retrying: {step_id} in {execution_id}",
            component="ExecutionController",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionStepRetrying", {"execution_id": execution_id, "step_id": step_id}
        )

    def override_decision(
        self,
        execution_id: str,
        checkpoint: dict[str, Any],
        decision_data: dict[str, Any],
    ) -> None:
        """Override a step outcome or variable state directly."""
        updated_variables = {
            **checkpoint["workflow_variables"],
            **decision_data.get("variables", {}),
        }
        updated_outputs = {
            **checkpoint["step_outputs"],
            **decision_data.get("outputs", {}),
        }

        CheckpointManager.save_checkpoint(
            execution_id=execution_id,
            workflow_id=checkpoint["workflow_id"],
            workflow_version=checkpoint["workflow_version"],
            schema_version=checkpoint["schema_version"],
            checkpoint_version=checkpoint["checkpoint_version"],
            current_status=ExecutionStateTransition.RUNNING.value,
            current_stage=checkpoint["current_stage"],
            completed_steps=checkpoint["completed_steps"],
            skipped_steps=checkpoint["skipped_steps"],
            failed_steps=checkpoint["failed_steps"],
            step_outputs=updated_outputs,
            workflow_variables=updated_variables,
            execution_metadata=checkpoint["execution_metadata"],
        )
        logger.info(
            EventID.LOG_INFO,
            f"Execution decision overridden: {execution_id}",
            component="ExecutionController",
        )
        DomainEventDispatcher.dispatch(
            "ExecutionDecisionOverridden", {"execution_id": execution_id}
        )


class InterventionEngine:
    """Core HITL Intervention Engine orchestrating execution controls and policies."""

    def __init__(
        self,
        pause_manager: PauseManager | None = None,
        resume_manager: ResumeManager | None = None,
        controller: ExecutionController | None = None,
    ) -> None:
        self.pause_manager = pause_manager or PauseManager()
        self.resume_manager = resume_manager or ResumeManager()
        self.controller = controller or ExecutionController()
        init_interventions_table()

    def process_intervention(self, request: InterventionRequest) -> bool:
        """Process intervention request validating policies, permissions, and checkpoint states."""
        execution_id = request.execution_id
        action = request.action
        policy = request.policy

        # 1. Validate: Execution exists (load checkpoint)
        checkpoint = CheckpointManager.load_checkpoint(execution_id)
        if not checkpoint:
            logger.warning(
                EventID.LOG_WARNING,
                f"Intervention rejected: execution {execution_id} does not exist",
                component="InterventionEngine",
            )
            DomainEventDispatcher.dispatch(
                "InterventionRejected",
                {"execution_id": execution_id, "reason": "Execution does not exist"},
            )
            self._record_history(request, checkpoint_state="None", success=False)
            return False

        current_status = checkpoint["current_status"]
        is_valid = True
        reject_reason = ""

        # 2. Validate: Policy compliance & authorization checks
        if policy == InterventionPolicy.EMERGENCY_STOP:
            if action not in (InterventionAction.CANCEL, InterventionAction.PAUSE):
                is_valid = False
                reject_reason = (
                    f"Action {action.value} not allowed under EMERGENCY_STOP policy"
                )

        elif policy == InterventionPolicy.MANUAL_ONLY:
            if request.user_role not in ("Operator", "Admin", "Engineer"):
                is_valid = False
                reject_reason = (
                    f"User role '{request.user_role}' unauthorized for manual control"
                )

        elif policy == InterventionPolicy.ADMIN_OVERRIDE:
            if request.user_role != "Admin":
                is_valid = False
                reject_reason = (
                    f"User role '{request.user_role}' must be Admin for override policy"
                )

        elif policy == InterventionPolicy.APPROVAL_REQUIRED:
            if not request.approval_id:
                is_valid = False
                reject_reason = "Missing required approval reference"
            else:
                db_path = sqlite_db_manager.db_path
                conn = sqlite3.connect(db_path)
                approved = False
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='approval_sessions'"
                    )
                    if cursor.fetchone()[0] > 0:
                        cursor.execute(
                            "SELECT status FROM approval_sessions WHERE approval_id = ?",
                            (request.approval_id,),
                        )
                        row = cursor.fetchone()
                        if row and row[0] == "Approved":
                            approved = True
                    else:
                        approved = request.metadata.get("approval_status") == "Approved"
                except Exception as e:
                    logger.error(
                        EventID.LOG_ERROR,
                        f"Error verifying approval completion: {e}",
                        component="InterventionEngine",
                    )
                finally:
                    conn.close()

                if not approved:
                    is_valid = False
                    reject_reason = (
                        f"Approval workflow '{request.approval_id}' is not approved"
                    )

        # 3. Validate: Execution State transitions
        if is_valid:
            if action == InterventionAction.PAUSE:
                if current_status not in (
                    "Running",
                    "validated",
                    "queued",
                    ExecutionStateTransition.RUNNING.value,
                ):
                    is_valid = False
                    reject_reason = (
                        f"Cannot pause execution in state '{current_status}'"
                    )
            elif action == InterventionAction.RESUME:
                if current_status not in (
                    ExecutionStateTransition.PAUSED.value,
                    "Paused",
                ):
                    is_valid = False
                    reject_reason = (
                        f"Cannot resume execution in state '{current_status}'"
                    )
            elif action == InterventionAction.CANCEL:
                if current_status in (
                    ExecutionStateTransition.CANCELLED.value,
                    "Cancelled",
                    "Completed",
                    "Failed",
                ):
                    is_valid = False
                    reject_reason = (
                        f"Cannot cancel resolved execution in state '{current_status}'"
                    )
            elif action == InterventionAction.RESTART_CHECKPOINT:
                if not checkpoint or not checkpoint.get("completed_steps"):
                    is_valid = False
                    reject_reason = f"No valid checkpoint recovery steps for restart in {execution_id}"
            elif action in (
                InterventionAction.SKIP_STEP,
                InterventionAction.RETRY_STEP,
            ) and not request.metadata.get("step_id"):
                is_valid = False
                reject_reason = f"Missing step_id for {action.value} action"

        # 4. Handle rejection or execute action
        if not is_valid:
            logger.warning(
                EventID.LOG_WARNING,
                f"Intervention rejected: {reject_reason}",
                component="InterventionEngine",
            )
            self._record_history(
                request, checkpoint_state=current_status, success=False
            )
            return False

        # Execute Action
        if action == InterventionAction.PAUSE:
            self.pause_manager.pause_execution(execution_id, checkpoint)
        elif action == InterventionAction.RESUME:
            self.resume_manager.resume_execution(execution_id, checkpoint)
        elif action == InterventionAction.CANCEL:
            self.controller.cancel_execution(execution_id, checkpoint)
        elif action == InterventionAction.RESTART_CHECKPOINT:
            self.controller.restart_from_checkpoint(execution_id, checkpoint)
        elif action == InterventionAction.RESTART_BEGINNING:
            self.controller.restart_from_beginning(execution_id, checkpoint)
        elif action == InterventionAction.SKIP_STEP:
            step_id = request.metadata.get("step_id", "")
            self.controller.skip_current_step(execution_id, checkpoint, step_id)
        elif action == InterventionAction.RETRY_STEP:
            step_id = request.metadata.get("step_id", "")
            self.controller.retry_current_step(execution_id, checkpoint, step_id)
        elif action == InterventionAction.OVERRIDE_DECISION:
            decision_data = request.metadata.get("decision_data", {})
            self.controller.override_decision(execution_id, checkpoint, decision_data)
        elif action == InterventionAction.CONTINUE:
            CheckpointManager.save_checkpoint(
                execution_id=execution_id,
                workflow_id=checkpoint["workflow_id"],
                workflow_version=checkpoint["workflow_version"],
                schema_version=checkpoint["schema_version"],
                checkpoint_version=checkpoint["checkpoint_version"],
                current_status=ExecutionStateTransition.RUNNING.value,
                current_stage=checkpoint["current_stage"],
                completed_steps=checkpoint["completed_steps"],
                skipped_steps=checkpoint["skipped_steps"],
                failed_steps=checkpoint["failed_steps"],
                step_outputs=checkpoint["step_outputs"],
                workflow_variables=checkpoint["workflow_variables"],
                execution_metadata=checkpoint["execution_metadata"],
            )

        self._record_history(request, checkpoint_state=current_status, success=True)
        return True

    def _record_history(
        self, request: InterventionRequest, checkpoint_state: str, success: bool
    ) -> None:
        """Log intervention to the persistent database history."""
        import uuid

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            entry_id = str(uuid.uuid4())
            state_after = checkpoint_state
            if success:
                if request.action == InterventionAction.PAUSE:
                    state_after = ExecutionStateTransition.PAUSED.value
                elif request.action == InterventionAction.RESUME:
                    state_after = ExecutionStateTransition.RUNNING.value
                elif request.action == InterventionAction.CANCEL:
                    state_after = ExecutionStateTransition.CANCELLED.value
                elif request.action == InterventionAction.RESTART_CHECKPOINT:
                    state_after = ExecutionStateTransition.RESTARTED.value
                elif request.action in (
                    InterventionAction.RESTART_BEGINNING,
                    InterventionAction.SKIP_STEP,
                    InterventionAction.RETRY_STEP,
                    InterventionAction.OVERRIDE_DECISION,
                    InterventionAction.CONTINUE,
                ):
                    state_after = ExecutionStateTransition.RUNNING.value

            cursor.execute(
                """
                INSERT INTO workflow_interventions (
                    entry_id, execution_id, action, policy, state_before, state_after, user_id, timestamp, success, comments, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    request.execution_id,
                    request.action.value,
                    request.policy.value,
                    checkpoint_state,
                    state_after,
                    request.user_id,
                    time.time(),
                    1 if success else 0,
                    request.metadata.get("comments"),
                    json.dumps(request.metadata),
                ),
            )
            conn.commit()

            # Trim history to max limit configured
            max_history = platform_settings.HITL_MAX_INTERVENTION_HISTORY
            cursor.execute("SELECT COUNT(*) FROM workflow_interventions")
            count = cursor.fetchone()[0]
            if count > max_history:
                # Delete oldest entries
                cursor.execute(
                    """
                    DELETE FROM workflow_interventions WHERE entry_id IN (
                        SELECT entry_id FROM workflow_interventions ORDER BY timestamp ASC LIMIT ?
                    )
                    """,
                    (count - max_history,),
                )
                conn.commit()

        except Exception as e:
            logger.error(
                EventID.LOG_ERROR,
                f"Failed to record intervention history: {e}",
                component="InterventionEngine",
            )
        finally:
            conn.close()

    def get_history(
        self, execution_id: str | None = None
    ) -> list[InterventionHistoryEntry]:
        """Fetch historical intervention log entries."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        entries = []
        try:
            cursor = conn.cursor()
            if execution_id:
                cursor.execute(
                    "SELECT entry_id, execution_id, action, policy, state_before, state_after, user_id, timestamp, success, comments FROM workflow_interventions WHERE execution_id = ? ORDER BY timestamp DESC",
                    (execution_id,),
                )
            else:
                cursor.execute(
                    "SELECT entry_id, execution_id, action, policy, state_before, state_after, user_id, timestamp, success, comments FROM workflow_interventions ORDER BY timestamp DESC"
                )
            rows = cursor.fetchall()
            for r in rows:
                entries.append(
                    InterventionHistoryEntry(
                        entry_id=r[0],
                        execution_id=r[1],
                        action=r[2],
                        policy=r[3],
                        state_before=r[4],
                        state_after=r[5],
                        user_id=r[6],
                        timestamp=r[7],
                        success=bool(r[8]),
                        comments=r[9],
                    )
                )
        finally:
            conn.close()
        return entries

    def get_metrics(self) -> InterventionStatistics:
        """Compile and calculate intervention metrics from database history logs."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        stats = InterventionStatistics()
        try:
            cursor = conn.cursor()
            # Basic counts
            cursor.execute(
                "SELECT COUNT(*) FROM workflow_interventions WHERE action = ?",
                (InterventionAction.PAUSE.value,),
            )
            stats.pause_requests = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_interventions WHERE action = ?",
                (InterventionAction.RESUME.value,),
            )
            stats.resume_requests = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_interventions WHERE action = ?",
                (InterventionAction.CANCEL.value,),
            )
            stats.cancel_requests = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_interventions WHERE action IN (?, ?)",
                (
                    InterventionAction.RESTART_CHECKPOINT.value,
                    InterventionAction.RESTART_BEGINNING.value,
                ),
            )
            stats.restart_requests = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_interventions WHERE action = ?",
                (InterventionAction.OVERRIDE_DECISION.value,),
            )
            stats.override_requests = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*), SUM(success) FROM workflow_interventions")
            row = cursor.fetchone()
            total = row[0] if row else 0
            successful = row[1] if row and row[1] is not None else 0
            stats.intervention_success_rate = (
                (successful / total * 100.0) if total > 0 else 100.0
            )

            # Calculate average pause duration and resume latency from details
            cursor.execute(
                "SELECT execution_id, action, timestamp, metadata FROM workflow_interventions ORDER BY timestamp ASC"
            )
            events = cursor.fetchall()

            pauses = {}
            pause_durations = []
            resume_latencies = []

            for execution_id, action, timestamp, metadata_str in events:
                metadata = {}
                with contextlib.suppress(Exception):
                    if metadata_str:
                        metadata = json.loads(metadata_str)

                if action == InterventionAction.PAUSE.value:
                    pauses[execution_id] = timestamp
                elif action == InterventionAction.RESUME.value:
                    if execution_id in pauses:
                        pause_durations.append(timestamp - pauses[execution_id])
                        del pauses[execution_id]
                    latency = metadata.get("resume_latency")
                    if latency is not None:
                        resume_latencies.append(latency)

            stats.average_pause_duration = (
                sum(pause_durations) / len(pause_durations) if pause_durations else 0.0
            )
            stats.average_resume_latency = (
                sum(resume_latencies) / len(resume_latencies)
                if resume_latencies
                else 0.0
            )

        finally:
            conn.close()
        return stats
