"""Telemetry logger for the Observability module itself."""

from app.core.logging.logging import logger
from app.telemetry.events import EventID


class ObservabilityTelemetry:
    """Manages telemetry logs for the Observability module."""

    @staticmethod
    def log_report_generated(execution_id: str, status: str, stages_count: int) -> None:
        """Log report generated event."""
        logger.info(
            EventID.LOG_INFO,
            f"Execution report generated successfully for run '{execution_id}' (Status: {status}, Stages: {stages_count}).",
            component="Observability",
            execution_id=execution_id,
            status=status,
            stages=stages_count,
        )
