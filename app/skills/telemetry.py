from typing import Any

from app.core.logging.logging import logger
from app.skills.base import BaseSkill
from app.skills.context import SkillContext
from app.telemetry.events import EventID


class SkillTelemetry:
    """Helper formatting and writing structured logs for AI Skill execution."""

    @staticmethod
    def log_skill_started(skill: BaseSkill[Any, Any], context: SkillContext) -> None:
        """Log skill start event to the telemetry framework."""
        logger.info(
            EventID.LOG_INFO,
            "AI Skill execution started",
            component="SkillExecutor",
            skill_name=skill.name,
            skill_version=skill.version,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            job_id=context.job_id,
        )

    @staticmethod
    def log_skill_success(
        skill: BaseSkill[Any, Any], context: SkillContext, latency_ms: float
    ) -> None:
        """Log skill execution success with latency tracking details."""
        logger.info(
            EventID.LOG_INFO,
            "AI Skill execution completed successfully",
            component="SkillExecutor",
            skill_name=skill.name,
            skill_version=skill.version,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            job_id=context.job_id,
            latency_ms=round(latency_ms, 2),
        )

    @staticmethod
    def log_skill_failure(
        skill: BaseSkill[Any, Any],
        context: SkillContext,
        exc: Exception,
        latency_ms: float,
    ) -> None:
        """Log skill failure warning/error details along with duration metrics."""
        logger.error(
            EventID.LOG_ERROR,
            f"AI Skill execution failed: {exc}",
            component="SkillExecutor",
            skill_name=skill.name,
            skill_version=skill.version,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            job_id=context.job_id,
            latency_ms=round(latency_ms, 2),
            error_class=type(exc).__name__,
        )
