"""Hybrid Seeder orchestrator combining deterministic and AI-assisted generation."""

import time
from typing import Any

from app.llm.gateway import LLMGateway
from app.seeder.ai import AIStrategy
from app.seeder.deterministic import DeterministicStrategy
from app.seeder.exceptions import (
    GenerationException,
    StrategySelectionException,
    ValidationException,
)
from app.seeder.models import (
    FieldDefinition,
    GeneratedRecord,
    GenerationStatistics,
    GenerationStrategy,
    SeedRequest,
    SeedResult,
)
from app.seeder.strategy import StrategyRegistry, strategy_registry
from app.seeder.telemetry import SeederTelemetry
from app.seeder.validator import SeederValidator
from app.workers.models import ExecutionUnit


class HybridSeeder:
    """Enterprise Hybrid Seeder coordinating deterministic and AI synthetic data generation."""

    def __init__(
        self,
        gateway: LLMGateway | None = None,
        deterministic_strategy: DeterministicStrategy | None = None,
        ai_strategy: AIStrategy | None = None,
        registry: StrategyRegistry | None = None,
    ) -> None:
        """Initialize the HybridSeeder.

        Args:
            gateway: LLM gateway instance for AI generation.
            deterministic_strategy: Specific deterministic generation strategy.
            ai_strategy: Specific AI generation strategy.
            registry: Registry containing field-to-strategy mappings.
        """
        self.gateway = gateway or LLMGateway()
        self.deterministic_strategy = deterministic_strategy or DeterministicStrategy()
        self.ai_strategy = ai_strategy or AIStrategy(gateway=self.gateway)
        self.registry = registry or strategy_registry

    def select_strategy(self, fields: dict[str, FieldDefinition]) -> tuple[
        GenerationStrategy,
        dict[str, FieldDefinition],
        dict[str, FieldDefinition],
    ]:
        """Select the appropriate generation strategy by classifying request fields.

        Args:
            fields: Map of field names to their generation definitions.

        Returns:
            Tuple: (overall strategy, deterministic fields dict, AI fields dict).
        """
        deterministic_fields: dict[str, FieldDefinition] = {}
        ai_fields: dict[str, FieldDefinition] = {}

        for name, field_def in fields.items():
            field_type = field_def.type.lower()
            strategy = self.registry.get_strategy(field_type)

            if strategy == GenerationStrategy.DETERMINISTIC:
                deterministic_fields[name] = field_def
            elif strategy == GenerationStrategy.AI:
                ai_fields[name] = field_def
            elif (
                "values" in field_def.rules
                or "min" in field_def.rules
                or "max" in field_def.rules
            ):
                deterministic_fields[name] = field_def
            else:
                raise StrategySelectionException(
                    f"Unrecognized field type '{field_def.type}' for field '{name}' "
                    "and no rules could resolve the strategy."
                )

        if deterministic_fields and ai_fields:
            overall_strategy = GenerationStrategy.HYBRID
        elif ai_fields:
            overall_strategy = GenerationStrategy.AI
        else:
            overall_strategy = GenerationStrategy.DETERMINISTIC

        return overall_strategy, deterministic_fields, ai_fields

    async def seed(self, request: SeedRequest) -> SeedResult:
        """Execute synthetic data generation from a typed SeedRequest.

        Args:
            request: The generation specification container.

        Returns:
            SeedResult: The generated records and execution metadata.
        """
        start_time = time.perf_counter()

        # 1. Select Strategy
        overall_strategy, det_fields, ai_fields = self.select_strategy(request.fields)

        # Log startup
        SeederTelemetry.log_generation_started(
            request.target, request.num_records, overall_strategy.value
        )

        try:
            # 2. Generate fields
            det_results: list[dict[str, Any]] = []
            ai_results: list[dict[str, Any]] = []

            if det_fields:
                det_results = await self.deterministic_strategy.generate(
                    det_fields,
                    request.num_records,
                    target=request.target,
                    seed=request.seed,
                )

            if ai_fields:
                ai_results = await self.ai_strategy.generate(
                    ai_fields,
                    request.num_records,
                    target=request.target,
                    seed=request.seed,
                )

            # 3. Combine results
            records: list[GeneratedRecord] = []
            for i in range(request.num_records):
                merged_data: dict[str, Any] = {}
                strategy_used: dict[str, GenerationStrategy] = {}

                if det_fields and i < len(det_results):
                    merged_data.update(det_results[i])
                    for name in det_fields:
                        strategy_used[name] = GenerationStrategy.DETERMINISTIC

                if ai_fields and i < len(ai_results):
                    merged_data.update(ai_results[i])
                    for name in ai_fields:
                        strategy_used[name] = GenerationStrategy.AI

                # 4. Validate record
                validation_errors = SeederValidator.validate_record(
                    merged_data, request.fields
                )
                validation_passed = len(validation_errors) == 0

                records.append(
                    GeneratedRecord(
                        data=merged_data,
                        validation_passed=validation_passed,
                        errors=validation_errors,
                        strategy_used=strategy_used,
                    )
                )

            # 5. Compile Statistics
            successful_records = sum(1 for r in records if r.validation_passed)
            failed_records = len(records) - successful_records

            if request.strict and failed_records > 0:
                all_errors = []
                for r in records:
                    all_errors.extend(r.errors)
                raise ValidationException(
                    f"Record validation failed in strict mode: {'; '.join(all_errors)}"
                )

            # Retrieve measured LLM metrics from the AI strategy
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            estimated_cost = 0.0
            llm_latency_ms = 0.0

            if ai_fields and self.ai_strategy.last_metadata:
                m = self.ai_strategy.last_metadata
                prompt_tokens = m.prompt_tokens
                completion_tokens = m.completion_tokens
                total_tokens = m.total_tokens
                estimated_cost = m.estimated_cost
                llm_latency_ms = m.latency_ms

            stats = GenerationStatistics(
                total_records=request.num_records,
                successful_records=successful_records,
                failed_records=failed_records,
                deterministic_fields_count=len(det_fields) * request.num_records,
                ai_fields_count=len(ai_fields) * request.num_records,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                latency_ms=llm_latency_ms,
            )

            success = failed_records == 0
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            result = SeedResult(
                target=request.target,
                records=records,
                statistics=stats,
                success=success,
            )

            # Log completion
            SeederTelemetry.log_generation_completed(
                request.target, success, stats, duration_ms
            )
            return result

        except ValidationException as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            SeederTelemetry.log_generation_failed(request.target, str(exc), duration_ms)
            raise exc
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            SeederTelemetry.log_generation_failed(request.target, str(exc), duration_ms)
            raise GenerationException(
                f"Synthetic data generation failed: {exc}"
            ) from exc

    async def execute_unit(self, unit: ExecutionUnit) -> dict[str, Any]:
        """Worker framework adapter mapping ExecutionUnit payload to SeedRequest and execution.

        Args:
            unit: The typed execution unit container.

        Returns:
            dict[str, Any]: Model dump of the SeedResult.
        """
        payload = unit.payload
        num_records = payload.get("num_records", 1)
        raw_fields = payload.get("fields", {})
        seed = payload.get("seed")
        strict = payload.get("strict", False)

        fields = {}
        for name, spec in raw_fields.items():
            fields[name] = FieldDefinition(
                type=spec.get("type", "string"),
                rules=spec.get("rules", {}),
                required=spec.get("required", True),
            )

        request = SeedRequest(
            target=unit.target,
            num_records=num_records,
            fields=fields,
            seed=seed,
            strict=strict,
        )

        result = await self.seed(request)
        return result.model_dump()
