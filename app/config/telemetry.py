"""Telemetry logging helper for runtime configuration actions."""

from app.core.logging.logging import logger
from app.telemetry.events import EventID


class ConfigurationTelemetry:
    """Manages telemetry logs for the configuration package."""

    @staticmethod
    def log_config_loaded(profile: str, sources_count: int, status: str) -> None:
        """Log configuration loaded or reloaded events."""
        logger.info(
            EventID.LOG_INFO,
            f"Runtime configuration loaded (Profile: {profile}, Sources: {sources_count}, Status: {status}).",
            component="Configuration",
            profile=profile,
            sources=sources_count,
            status=status,
        )

    @staticmethod
    def log_config_validation_failed(error_msg: str) -> None:
        """Log warning when validation fails."""
        logger.warning(
            EventID.LOG_WARNING,
            f"Configuration validation failed: {error_msg}",
            component="Configuration",
            error=error_msg,
        )
