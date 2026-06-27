"""Structured telemetry logging for the Export Engine."""

from app.core.logging.logging import logger
from app.export.models import ExportStatistics
from app.telemetry.events import EventID


class ExportTelemetry:
    """Manages telemetry logs for Export Engine execution."""

    @staticmethod
    def log_export_started(
        execution_id: str, format_name: str, table_count: int
    ) -> None:
        """Log export started."""
        logger.info(
            EventID.EXPORT_STARTED,
            f"Export Engine execution started (Format: {format_name}, Tables: {table_count}).",
            component="ExportEngine",
            execution_id=execution_id,
            format=format_name,
        )

    @staticmethod
    def log_export_completed(
        execution_id: str,
        success: bool,
        stats: ExportStatistics,
        duration_ms: float,
    ) -> None:
        """Log export completed."""
        event_id = EventID.EXPORT_COMPLETED if success else EventID.EXPORT_FAILED
        status_msg = "successfully" if success else "with validation/export failures"
        logger.info(
            event_id,
            f"Export Engine execution completed {status_msg}.",
            component="ExportEngine",
            execution_id=execution_id,
            success=success,
            duration_ms=round(duration_ms, 2),
            total_records=stats.total_records,
            total_tables=stats.total_tables,
            file_size_bytes=stats.file_size_bytes,
        )

    @staticmethod
    def log_export_failed(
        execution_id: str, error_msg: str, duration_ms: float
    ) -> None:
        """Log export failed."""
        logger.error(
            EventID.EXPORT_FAILED,
            f"Export Engine critical failure: {error_msg}",
            component="ExportEngine",
            execution_id=execution_id,
            error=error_msg,
            duration_ms=round(duration_ms, 2),
        )

    @staticmethod
    def log_cleanup_failed(execution_id: str, file_path: str, error_msg: str) -> None:
        """Log transactional cleanup failed."""
        logger.warning(
            EventID.LOG_WARNING,
            f"Transactional export cleanup failed for file '{file_path}': {error_msg}",
            component="ExportEngine",
            execution_id=execution_id,
            file_path=file_path,
            error=error_msg,
        )
