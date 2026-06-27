"""Orchestrator running AI Skills, timing them, logging telemetry, and handling errors."""

import time

from app.skills.base import BaseSkill
from app.skills.exceptions import (
    SkillError,
    SkillExecutionError,
    SkillValidationError,
)
from app.skills.models import InputT, OutputT, SkillRequest, SkillResponse
from app.skills.telemetry import SkillTelemetry


class SkillExecutor:
    """Orchestrator running AI Skills, timing them, logging telemetry, and handling errors."""

    @staticmethod
    async def execute(
        skill: BaseSkill[InputT, OutputT], request: SkillRequest[InputT]
    ) -> SkillResponse[OutputT]:
        """Invoke a skill through its lifecycle steps: validate, prepare, execute, and post_process.

        Args:
            skill: The skill instance to execute.
            request: Unified request wrapping dynamic input parameters and execution context.

        Returns:
            SkillResponse[O]: Type-safe output or failed message with latency logs.
        """
        start_time = time.perf_counter()

        # Log skill start telemetry
        SkillTelemetry.log_skill_started(skill, request.context)

        try:
            # 1. Validate
            try:
                await skill.validate(request.input_data, request.context)
            except SkillValidationError:
                raise
            except Exception as exc:
                raise SkillValidationError(f"Input validation failed: {exc}") from exc

            # 2. Prepare
            try:
                prepared_data = await skill.prepare(request.input_data, request.context)
            except Exception as exc:
                raise SkillExecutionError(
                    f"Skill preparation stage failed: {exc}"
                ) from exc

            # 3. Execute
            try:
                raw_result = await skill.execute(prepared_data, request.context)
            except Exception as exc:
                raise SkillExecutionError(
                    f"Skill execution stage failed: {exc}"
                ) from exc

            # 4. Post-process
            try:
                final_output = await skill.post_process(raw_result, request.context)
            except Exception as exc:
                raise SkillExecutionError(
                    f"Skill post-processing stage failed: {exc}"
                ) from exc

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Log success telemetry
            SkillTelemetry.log_skill_success(skill, request.context, latency_ms)

            return SkillResponse[OutputT](
                success=True,
                data=final_output,
                error_message=None,
                latency_ms=round(latency_ms, 2),
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            error_message = str(exc)

            # Wrap standard/unhandled errors into SkillError subclass
            wrapped_exc = exc
            if not isinstance(exc, SkillError):
                wrapped_exc = SkillExecutionError(error_message)

            # Log failure telemetry
            SkillTelemetry.log_skill_failure(
                skill, request.context, wrapped_exc, latency_ms
            )

            return SkillResponse[OutputT](
                success=False,
                data=None,
                error_message=error_message,
                latency_ms=round(latency_ms, 2),
            )
