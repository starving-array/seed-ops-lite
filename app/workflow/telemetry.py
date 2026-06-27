"""Structured logging helper class for the Workflow Engine events."""

from app.core.logging.logging import logger
from app.telemetry.events import EventID
from app.workflow.models import WorkflowProgress, WorkflowState


class WorkflowTelemetry:
    """Manages telemetry logging calls for workflow state cycles and tasks."""

    @staticmethod
    def log_workflow_started(workflow_id: str, execution_id: str) -> None:
        """Log workflow initiation event."""
        logger.info(
            EventID.LOG_INFO,
            "Workflow execution started",
            component="WorkflowEngine",
            workflow_id=workflow_id,
            execution_id=execution_id,
        )

    @staticmethod
    def log_state_transition(
        workflow_id: str, old_state: WorkflowState, new_state: WorkflowState
    ) -> None:
        """Log workflow state transition."""
        logger.info(
            EventID.LOG_INFO,
            f"Workflow state transitioned from {old_state.value} to {new_state.value}",
            component="WorkflowEngine",
            workflow_id=workflow_id,
            old_state=old_state.value,
            new_state=new_state.value,
        )

    @staticmethod
    def log_progress_updated(workflow_id: str, progress: WorkflowProgress) -> None:
        """Log execution progress update."""
        logger.info(
            EventID.LOG_INFO,
            f"Workflow progress updated: {progress.progress_percentage}% completed",
            component="WorkflowEngine",
            workflow_id=workflow_id,
            completed_groups=progress.completed_groups,
            total_groups=progress.total_groups,
            progress_percentage=progress.progress_percentage,
        )

    @staticmethod
    def log_workflow_success(workflow_id: str, duration_ms: float) -> None:
        """Log workflow execution completion with total latency."""
        logger.info(
            EventID.LOG_INFO,
            "Workflow completed successfully",
            component="WorkflowEngine",
            workflow_id=workflow_id,
            duration_ms=round(duration_ms, 2),
        )

    @staticmethod
    def log_workflow_failure(
        workflow_id: str, exc: Exception, duration_ms: float
    ) -> None:
        """Log workflow failure event detailing caught exception."""
        logger.error(
            EventID.LOG_ERROR,
            f"Workflow execution failed: {exc}",
            component="WorkflowEngine",
            workflow_id=workflow_id,
            duration_ms=round(duration_ms, 2),
            error_class=type(exc).__name__,
        )
