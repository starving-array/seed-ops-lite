"""Telemetry logger wrapper for the CLI Application commands."""

from app.core.logging.logging import logger
from app.telemetry.events import EventID


class CLITelemetry:
    """Dispatches telemetric structured logs for CLI execution paths."""

    @staticmethod
    def log_cli_started(command: str, correlation_id: str) -> None:
        """Log CLI command execution startup."""
        logger.info(
            EventID.LOG_INFO,
            f"CLI execution started (Command: '{command}')",
            component="CLI",
            command=command,
            correlation_id=correlation_id,
        )

    @staticmethod
    def log_cli_completed(
        command: str, exit_code: int, duration_ms: float, correlation_id: str
    ) -> None:
        """Log CLI command execution completion."""
        logger.info(
            EventID.LOG_INFO,
            f"CLI execution completed (Command: '{command}', ExitCode: {exit_code}, Latency: {duration_ms:.2f}ms)",
            component="CLI",
            command=command,
            exit_code=exit_code,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
        )

    @staticmethod
    def log_cli_error(command: str, error_msg: str, correlation_id: str) -> None:
        """Log critical failures during CLI runs."""
        logger.error(
            EventID.LOG_ERROR,
            f"CLI execution failure in command '{command}': {error_msg}",
            component="CLI",
            command=command,
            error=error_msg,
            correlation_id=correlation_id,
        )
