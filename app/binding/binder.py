"""BindingEngine coordinating RelationshipResolver and ReferentialValidator."""

import time
import uuid
from typing import Any

from app.binding.models import (
    BindingRequest,
    BindingResult,
    BindingStatistics,
    BoundRecord,
    RelationshipReference,
)
from app.binding.resolver import RelationshipResolver
from app.binding.telemetry import BindingTelemetry
from app.binding.validator import ReferentialValidator
from app.workers.models import ExecutionUnit


class BindingEngine:
    """Enterprise-grade BindingEngine responsible for establishing foreign key references across tables."""

    def __init__(
        self,
        resolver: RelationshipResolver | None = None,
        validator: ReferentialValidator | None = None,
    ) -> None:
        """Initialize BindingEngine.

        Args:
            resolver: RelationshipResolver reference (or None).
            validator: ReferentialValidator reference (or None).
        """
        self.resolver = resolver or RelationshipResolver()
        self.validator = validator or ReferentialValidator()

    async def bind(self, request: BindingRequest) -> BindingResult:
        """Resolve and validate relationships between generated records.

        Args:
            request: BindingRequest input.

        Returns:
            BindingResult: Output including bound records and validation errors.
        """
        start_time = time.perf_counter()
        execution_id = str(uuid.uuid4())

        BindingTelemetry.log_binding_started(execution_id, len(request.records))

        try:
            # 1. Parse DDL and establish topological sorting
            ordered_tables, relationships = self.resolver.get_relationship_references(
                request.schema_ddl, request.relationships
            )

            # 2. Resolve relationships and bind parent keys into child records
            bound_records_dict, unresolved_count = self.resolver.resolve_relationships(
                request.records, ordered_tables, relationships
            )

            # 3. Validate referential integrity on the resolved dataset
            validation_errors = self.validator.validate(
                bound_records_dict, request.schema_ddl, relationships
            )

            success = len(validation_errors) == 0

            # Count total input records
            total_records = sum(len(recs) for recs in request.records.values())

            # Count bound records: count how many local columns we updated
            bound_count = 0
            for table_name, table_relationships in relationships.items():
                table_records = (
                    bound_records_dict.get(table_name)
                    or bound_records_dict.get(table_name.lower())
                    or []
                )
                for ref in table_relationships:
                    local_col = ref.local_column.lower()
                    for rec in table_records:
                        val = None
                        for k, v in rec.items():
                            if k.lower() == local_col:
                                val = v
                                break
                        if val is not None:
                            bound_count += 1

            # Convert bound_records_dict to the target BoundRecord model schema
            records_result: dict[str, list[BoundRecord]] = {}
            for t_name, rec_list in bound_records_dict.items():
                records_result[t_name] = [
                    BoundRecord(table_name=t_name, data=rec) for rec in rec_list
                ]

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            stats = BindingStatistics(
                total_records=total_records,
                bound_records=bound_count,
                unresolved_references_count=unresolved_count,
                integrity_violations_count=len(validation_errors),
                duration_ms=duration_ms,
            )

            result = BindingResult(
                records=records_result,
                statistics=stats,
                success=success,
                errors=validation_errors,
            )

            BindingTelemetry.log_binding_completed(
                execution_id, success, stats, duration_ms
            )
            return result

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            BindingTelemetry.log_binding_failed(execution_id, str(exc), duration_ms)
            return BindingResult(
                records={},
                statistics=BindingStatistics(duration_ms=duration_ms),
                success=False,
                errors=[str(exc)],
            )

    async def execute_unit(self, unit: ExecutionUnit) -> dict[str, Any]:
        """Worker framework adapter mapping ExecutionUnit payload to BindingRequest and execution.

        Args:
            unit: The typed execution unit container.

        Returns:
            dict[str, Any]: Model dump of the BindingResult.
        """
        payload = unit.payload
        raw_records = payload.get("records", {})
        schema_ddl = payload.get("schema_ddl", "")
        raw_relationships = payload.get("relationships", {})

        relationships = {}
        for table_name, ref_list in raw_relationships.items():
            relationships[table_name] = [
                RelationshipReference(
                    local_column=ref.get("local_column"),
                    referenced_table=ref.get("referenced_table"),
                    referenced_column=ref.get("referenced_column"),
                    relationship_type=ref.get("relationship_type", "many-to-one"),
                )
                for ref in ref_list
            ]

        request = BindingRequest(
            records=raw_records,
            schema_ddl=schema_ddl,
            relationships=relationships,
        )

        result = await self.bind(request)
        return result.model_dump()
