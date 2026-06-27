"""Structured telemetry logging for the Binding Engine."""

from app.binding.models import BindingStatistics
from app.core.logging.logging import logger
from app.telemetry.events import EventID


class BindingTelemetry:
    """Manages telemetry logs for Binding Engine execution."""

    @staticmethod
    def log_binding_started(execution_id: str, table_count: int) -> None:
        """Log binding started."""
        logger.info(
            EventID.LOG_INFO,
            f"Binding Engine execution started (Tables: {table_count}).",
            component="BindingEngine",
            execution_id=execution_id,
        )

    @staticmethod
    def log_binding_completed(
        execution_id: str,
        success: bool,
        stats: BindingStatistics,
        duration_ms: float,
    ) -> None:
        """Log binding completed."""
        event_id = EventID.LOG_INFO if success else EventID.LOG_ERROR
        status_msg = "successfully" if success else "with integrity violations"
        logger.info(
            event_id,
            f"Binding Engine execution completed {status_msg}.",
            component="BindingEngine",
            execution_id=execution_id,
            success=success,
            duration_ms=round(duration_ms, 2),
            total_records=stats.total_records,
            bound_records=stats.bound_records,
            unresolved_references=stats.unresolved_references_count,
            integrity_violations=stats.integrity_violations_count,
        )

    @staticmethod
    def log_binding_failed(
        execution_id: str, error_msg: str, duration_ms: float
    ) -> None:
        """Log binding failed."""
        logger.error(
            EventID.LOG_ERROR,
            f"Binding Engine critical failure: {error_msg}",
            component="BindingEngine",
            execution_id=execution_id,
            error=error_msg,
            duration_ms=round(duration_ms, 2),
        )
