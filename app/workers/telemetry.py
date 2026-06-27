"""Structured telemetry logging helper for the Worker Framework."""

from app.core.logging.logging import logger
from app.telemetry.events import EventID


class WorkerTelemetry:
    """Manages structured telemetry logs for worker execution lifecycle."""

    @staticmethod
    def log_worker_started(worker_id: str) -> None:
        """Log worker startup."""
        logger.info(
            EventID.WORKER_STARTED,
            f"Worker '{worker_id}' has started.",
            component="WorkerFramework",
            worker_id=worker_id,
        )

    @staticmethod
    def log_worker_stopped(worker_id: str) -> None:
        """Log worker shutdown/stop."""
        logger.info(
            EventID.WORKER_STOPPED,
            f"Worker '{worker_id}' has stopped.",
            component="WorkerFramework",
            worker_id=worker_id,
        )

    @staticmethod
    def log_worker_heartbeat(worker_id: str, is_healthy: bool) -> None:
        """Log worker heartbeat/health status."""
        logger.debug(
            EventID.WORKER_HEARTBEAT,
            f"Worker '{worker_id}' heartbeat. Healthy: {is_healthy}.",
            component="WorkerFramework",
            worker_id=worker_id,
            is_healthy=is_healthy,
        )

    @staticmethod
    def log_execution_started(worker_id: str, unit_id: str) -> None:
        """Log that a worker has begun executing a unit."""
        logger.info(
            EventID.JOB_STARTED,
            f"Worker '{worker_id}' started executing unit '{unit_id}'.",
            component="WorkerFramework",
            worker_id=worker_id,
            unit_id=unit_id,
        )

    @staticmethod
    def log_execution_completed(
        worker_id: str, unit_id: str, duration_ms: float, success: bool
    ) -> None:
        """Log that a worker has completed executing a unit."""
        event_id = EventID.JOB_COMPLETED if success else EventID.JOB_FAILED
        status_msg = "successfully" if success else "with failure"
        logger.info(
            event_id,
            f"Worker '{worker_id}' finished executing unit '{unit_id}' {status_msg}.",
            component="WorkerFramework",
            worker_id=worker_id,
            unit_id=unit_id,
            duration_ms=round(duration_ms, 2),
            success=success,
        )
