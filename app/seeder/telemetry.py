"""Structured telemetry logging for the Hybrid Seeder."""

from app.core.logging.logging import logger
from app.seeder.models import GenerationStatistics
from app.telemetry.events import EventID


class SeederTelemetry:
    """Manages structured logging for synthetic data seeding operations."""

    @staticmethod
    def log_generation_started(target: str, count: int, strategy: str) -> None:
        """Log the start of a seeding generation task."""
        logger.info(
            EventID.LOG_INFO,
            f"Seeder generation started for target '{target}' (Count: {count}, Strategy: {strategy}).",
            component="HybridSeeder",
            target=target,
            count=count,
            strategy=strategy,
        )

    @staticmethod
    def log_generation_completed(
        target: str,
        success: bool,
        stats: GenerationStatistics,
        duration_ms: float,
    ) -> None:
        """Log the successful completion or failure of a seeding task."""
        event_id = EventID.LOG_INFO if success else EventID.LOG_ERROR
        status_msg = "successfully" if success else "with failures"
        logger.info(
            event_id,
            f"Seeder generation completed {status_msg} for target '{target}'.",
            component="HybridSeeder",
            target=target,
            success=success,
            duration_ms=round(duration_ms, 2),
            total_records=stats.total_records,
            successful_records=stats.successful_records,
            failed_records=stats.failed_records,
            deterministic_fields=stats.deterministic_fields_count,
            ai_fields=stats.ai_fields_count,
            prompt_tokens=stats.prompt_tokens,
            completion_tokens=stats.completion_tokens,
            total_tokens=stats.total_tokens,
            estimated_cost=stats.estimated_cost,
            llm_latency_ms=stats.latency_ms,
        )

    @staticmethod
    def log_generation_failed(target: str, error_msg: str, duration_ms: float) -> None:
        """Log a critical failure during the generation process."""
        logger.error(
            EventID.LOG_ERROR,
            f"Seeder generation critical failure for target '{target}': {error_msg}",
            component="HybridSeeder",
            target=target,
            error=error_msg,
            duration_ms=round(duration_ms, 2),
        )
