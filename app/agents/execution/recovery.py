"""Agent Execution Recovery, Cancellation, Retry & Checkpointing Manager."""

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.execution.models import (
    ExecutionContext,
    ExecutionSession,
    ExecutionState,
)
from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.providers.sqlite import DomainEventDispatcher
from app.telemetry.events import EventID
from app.workflow.execution import CheckpointManager


class RecoveryStatistics(BaseModel):
    """Execution recovery statistical counters."""

    model_config = ConfigDict(frozen=True)

    checkpoints_created: int = 0
    checkpoints_restored: int = 0
    recoveries: int = 0
    recoveries_failed: int = 0
    retries: int = 0
    retry_failures: int = 0
    cancellations: int = 0
    average_recovery_time: float = 0.0


class RecoveryResult(BaseModel):
    """Summary outcome detail from a recovery invocation attempt."""

    model_config = ConfigDict(frozen=True)

    success: bool
    policy: str
    restored_stage: int = 0
    statistics: RecoveryStatistics = Field(default_factory=RecoveryStatistics)
    error_message: str | None = None


class ExecutionCheckpointAdapter:
    """Bridges Execution resilience to the core Workflow Checkpoint Manager."""

    @staticmethod
    def save_checkpoint(
        context: ExecutionContext,
        state: ExecutionState,
        completed_tasks: list[str],
        pending_tasks: list[str],
        retry_counters: dict[str, int],
        metadata: dict[str, Any],
    ) -> None:
        """Serialize current execution parameters into the Workflow Checkpoint tables."""
        logger.info(
            EventID.LOG_INFO,
            f"Checkpoint saved for execution: {context.execution_id}",
            component="ExecutionCheckpointAdapter",
        )
        CheckpointManager.save_checkpoint(
            execution_id=context.execution_id,
            workflow_id=context.workflow_id,
            workflow_version=context.workflow_version,
            schema_version=1,
            checkpoint_version="1.0.0",
            current_status=state.value,
            current_stage=0,
            completed_steps=completed_tasks,
            skipped_steps=[],
            failed_steps=pending_tasks,
            step_outputs={},
            workflow_variables=context.variables,
            execution_metadata={
                "retry_counters": retry_counters,
                **metadata,
            },
        )
        DomainEventDispatcher.dispatch(
            "CheckpointCreated",
            {"execution_id": context.execution_id, "state": state.value},
        )

    @staticmethod
    def load_checkpoint(execution_id: str) -> dict[str, Any] | None:
        """Load and deserialize checkpoint states."""
        raw = CheckpointManager.load_checkpoint(execution_id)
        if not raw:
            return None
        logger.info(
            EventID.LOG_INFO,
            f"Checkpoint restored for execution: {execution_id}",
            component="ExecutionCheckpointAdapter",
        )
        DomainEventDispatcher.dispatch(
            "CheckpointRestored",
            {"execution_id": execution_id},
        )
        return raw


class ExecutionRetryManager:
    """Manages immediate, delayed, and exponential backoff retry metadata."""

    def __init__(self) -> None:
        self._max_attempts = platform_settings.RECOVERY_MAX_ATTEMPTS
        self._default_delay = platform_settings.RECOVERY_RETRY_DELAY_SECONDS

    def should_retry(self, task_id: str, attempt_count: int) -> bool:
        """Assert whether execution should trigger another attempt for target task."""
        if attempt_count >= self._max_attempts:
            logger.warning(
                EventID.LOG_WARNING,
                f"Retry exhausted for task: {task_id}",
                component="ExecutionRetryManager",
            )
            DomainEventDispatcher.dispatch(
                "RetryExhausted",
                {"task_id": task_id, "attempt": attempt_count},
            )
            return False
        return True

    def get_next_retry_delay(self, task_id: str, attempt: int) -> float:
        """Calculate retry delay utilizing exponential backoff metadata metrics."""
        delay = self._default_delay * (2 ** (attempt - 1))
        logger.info(
            EventID.LOG_INFO,
            f"Retry scheduled for task: {task_id} in {delay}s",
            component="ExecutionRetryManager",
        )
        DomainEventDispatcher.dispatch(
            "RetryScheduled",
            {"task_id": task_id, "delay": delay, "attempt": attempt},
        )
        return float(delay)


class ExecutionCancellationManager:
    """Orchestrates structured task, stage, and execution cancellations."""

    def __init__(self) -> None:
        self._cancelled_sessions: dict[str, bool] = {}
        self._active_sessions: dict[str, ExecutionSession] = {}
        self._timeout = platform_settings.RECOVERY_CANCELLATION_TIMEOUT_SECONDS

    def register_session(self, session: ExecutionSession) -> None:
        """Register active execution session to track cancellation tokens."""
        self._active_sessions[session.execution_id] = session

    def cancel_execution(self, execution_id: str) -> None:
        """Trigger cancellation propagation for execution session."""
        logger.info(
            EventID.LOG_INFO,
            f"Execution cancelled: {execution_id}",
            component="ExecutionCancellationManager",
        )
        self._cancelled_sessions[execution_id] = True
        DomainEventDispatcher.dispatch(
            "ExecutionCancelled",
            {"execution_id": execution_id},
        )

    def is_cancelled(self, execution_id: str) -> bool:
        """Retrieve execution cancellation token status."""
        return self._cancelled_sessions.get(execution_id, False)


class ExecutionRecoveryManager:
    """Administers recovery policies to restore state and resume execution."""

    def __init__(self, cancellation_manager: ExecutionCancellationManager) -> None:
        self.cancellation_manager = cancellation_manager
        self._metrics = {
            "checkpoints_created": 0,
            "checkpoints_restored": 0,
            "recoveries": 0,
            "recoveries_failed": 0,
            "retries": 0,
            "retry_failures": 0,
            "cancellations": 0,
            "total_recovery_duration": 0.0,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Fetch recovery diagnostics counters."""
        return dict(self._metrics)

    async def recover_execution(
        self,
        execution_id: str,
        policy: str,
    ) -> RecoveryResult:
        """Execute recovery procedure using defined policy.

        Policies:
            Resume From Checkpoint
            Restart Stage
            Restart Execution
            Manual Recovery
            Abort Execution
        """
        start_time = time.perf_counter()
        self._metrics["recoveries"] += 1
        logger.info(
            EventID.LOG_INFO,
            f"Recovery started for execution: {execution_id} with policy: {policy}",
            component="ExecutionRecoveryManager",
        )
        DomainEventDispatcher.dispatch(
            "RecoveryStarted",
            {"execution_id": execution_id, "policy": policy},
        )

        try:
            # Validate checkpoint integrity
            checkpoint = ExecutionCheckpointAdapter.load_checkpoint(execution_id)
            if not checkpoint and policy != "Restart Execution":
                raise ValueError(
                    f"No valid checkpoint found for execution: {execution_id}"
                )

            self._metrics["checkpoints_restored"] += 1

            if policy == "Abort Execution":
                self.cancellation_manager.cancel_execution(execution_id)
                self._metrics["cancellations"] += 1

            duration = time.perf_counter() - start_time
            self._metrics["total_recovery_duration"] += duration

            avg_time = (
                self._metrics["total_recovery_duration"] / self._metrics["recoveries"]
                if self._metrics["recoveries"] > 0
                else 0.0
            )

            stats = RecoveryStatistics(
                checkpoints_created=int(self._metrics["checkpoints_created"]),
                checkpoints_restored=int(self._metrics["checkpoints_restored"]),
                recoveries=int(self._metrics["recoveries"]),
                recoveries_failed=int(self._metrics["recoveries_failed"]),
                retries=int(self._metrics["retries"]),
                retry_failures=int(self._metrics["retry_failures"]),
                cancellations=int(self._metrics["cancellations"]),
                average_recovery_time=avg_time,
            )

            logger.info(
                EventID.LOG_INFO,
                f"Recovery completed for execution: {execution_id}",
                component="ExecutionRecoveryManager",
            )
            DomainEventDispatcher.dispatch(
                "RecoveryCompleted",
                {"execution_id": execution_id},
            )

            return RecoveryResult(
                success=True,
                policy=policy,
                restored_stage=checkpoint["current_stage"] if checkpoint else 0,
                statistics=stats,
            )

        except Exception as exc:
            self._metrics["recoveries_failed"] += 1
            duration = time.perf_counter() - start_time
            self._metrics["total_recovery_duration"] += duration

            avg_time = (
                self._metrics["total_recovery_duration"] / self._metrics["recoveries"]
                if self._metrics["recoveries"] > 0
                else 0.0
            )

            stats = RecoveryStatistics(
                checkpoints_created=int(self._metrics["checkpoints_created"]),
                checkpoints_restored=int(self._metrics["checkpoints_restored"]),
                recoveries=int(self._metrics["recoveries"]),
                recoveries_failed=int(self._metrics["recoveries_failed"]),
                retries=int(self._metrics["retries"]),
                retry_failures=int(self._metrics["retry_failures"]),
                cancellations=int(self._metrics["cancellations"]),
                average_recovery_time=avg_time,
            )

            logger.error(
                EventID.LOG_ERROR,
                f"Recovery failed: {exc}",
                component="ExecutionRecoveryManager",
            )
            DomainEventDispatcher.dispatch(
                "RecoveryFailed",
                {"execution_id": execution_id, "error": str(exc)},
            )

            return RecoveryResult(
                success=False,
                policy=policy,
                statistics=stats,
                error_message=str(exc),
            )
