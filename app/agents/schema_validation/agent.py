"""Schema Validation Agent that coordinates validation skills and aggregates findings."""

import time
from typing import Any

from app.agents.schema_validation.aggregator import SchemaValidationAggregator
from app.agents.schema_validation.exceptions import SchemaValidationAgentException
from app.agents.schema_validation.models import SchemaValidationReport
from app.agents.schema_validation.planner import SchemaValidationPlanner
from app.core.logging.logging import logger
from app.llm.gateway import LLMGateway
from app.skills.context import SkillContext
from app.skills.executor import SkillExecutor
from app.skills.models import SkillRequest, SkillResponse
from app.skills.schema_validation.models import SchemaValidationInput
from app.telemetry.events import EventID


class SchemaValidationAgent:
    """Agent coordinating SQL schema validation skills sequentially and aggregating findings."""

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        """Initialize the agent with optional custom LLMGateway."""
        self.gateway = gateway or LLMGateway()
        self.planner = SchemaValidationPlanner()
        self.aggregator = SchemaValidationAggregator(gateway=self.gateway)

    async def validate_schema(
        self, schema_ddl: str, context: SkillContext | None = None
    ) -> SchemaValidationReport:
        """Orchestrate all schema validation skills sequentially and return a unified report.

        Args:
            schema_ddl: Raw database SQL schema DDL text.
            context: SkillContext for tracking and tracing.

        Returns:
            SchemaValidationReport: Deduplicated, sorted validation report.

        Raises:
            SchemaValidationAgentException: If execution planning, skill runs, or aggregation fail.
        """
        start_time = time.perf_counter()
        ctx = context or SkillContext()

        logger.info(
            EventID.LOG_INFO,
            "Schema Validation Agent execution started",
            component="SchemaValidationAgent",
            request_id=ctx.request_id,
            correlation_id=ctx.correlation_id,
        )

        try:
            # 1. Create execution plan
            plan = self.planner.plan()

            # 2. Run skills sequentially
            skill_responses: dict[str, SkillResponse[Any]] = {}
            for skill in plan:
                req = SkillRequest[SchemaValidationInput](
                    input_data=SchemaValidationInput(schema_ddl=schema_ddl),
                    context=ctx,
                )
                response = await SkillExecutor.execute(skill, req)
                skill_responses[skill.name] = response

            # 3. Compute total duration so far
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 4. Consolidate results into a single report
            report = await self.aggregator.aggregate(skill_responses, duration_ms)

            logger.info(
                EventID.LOG_INFO,
                "Schema Validation Agent completed successfully",
                component="SchemaValidationAgent",
                request_id=ctx.request_id,
                correlation_id=ctx.correlation_id,
                duration_ms=round(duration_ms, 2),
                overall_status=report.overall_status,
            )

            return report

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = str(exc)

            logger.error(
                EventID.LOG_ERROR,
                f"Schema Validation Agent execution failed: {error_msg}",
                component="SchemaValidationAgent",
                request_id=ctx.request_id,
                correlation_id=ctx.correlation_id,
                duration_ms=round(duration_ms, 2),
                error_class=type(exc).__name__,
            )

            if isinstance(exc, SchemaValidationAgentException):
                raise
            raise SchemaValidationAgentException(
                f"Agent execution failed: {error_msg}"
            ) from exc
