"""Guardian Planner responsible for generating database seeding execution plans."""

import hashlib
import re
import time
import uuid
from datetime import UTC, datetime

from app.agents.guardian.dependency_graph import DependencyGraph
from app.agents.guardian.exceptions import GuardianPlannerException
from app.agents.guardian.execution_plan import (
    ExecutionCostEstimate,
    ExecutionPlan,
    PlanningStatistics,
)
from app.agents.guardian.validators import validate_validation_report
from app.agents.schema_validation.models import SchemaValidationReport
from app.core.logging.logging import logger
from app.telemetry.events import EventID
from app.validation.ddl_validator import DDLValidator


class GuardianPlanner:
    """Planner transforming SQL schema DDL into a deterministic seeding execution strategy."""

    def __init__(self) -> None:
        """Initialize the GuardianPlanner."""
        self.version = "1.0.0"

    async def plan(
        self,
        schema_ddl: str,
        validation_report: SchemaValidationReport,
        row_targets: dict[str, int] | None = None,
    ) -> ExecutionPlan:
        """Generate a deterministic ExecutionPlan from SQL schema and validation details.

        Args:
            schema_ddl: Raw SQL DDL text.
            validation_report: Unified SchemaValidationReport from the agent.
            row_targets: Optional dict mapping table names to target row counts.

        Returns:
            ExecutionPlan: Deterministically sorted execution plan with cost heuristics.

        Raises:
            GuardianPlannerException: If schema validation failed, dependency loops exist,
                                      or missing tables are referenced.
        """
        start_time = time.perf_counter()
        execution_id = str(uuid.uuid4())
        schema_hash = hashlib.sha256(schema_ddl.encode("utf-8")).hexdigest()

        logger.info(
            EventID.LOG_INFO,
            "Guardian Planner execution started",
            component="GuardianPlanner",
            execution_id=execution_id,
            schema_hash=schema_hash,
        )

        try:
            # 1. Validate the validation report status first
            validate_validation_report(validation_report)

            # 2. Parse SQL DDL to extract tables and foreign keys
            ddl_validator = DDLValidator()
            ddl_validator.validate(schema_ddl)
            parsed_tables = ddl_validator.last_parsed_tables

            if not parsed_tables:
                raise GuardianPlannerException(
                    "No tables found in the provided DDL schema."
                )

            # 3. Construct dependency graph
            graph = DependencyGraph()
            declared_tables: set[str] = set()

            for _, table_def in parsed_tables.items():
                declared_tables.add(table_def.name)
                graph.add_node(table_def.name)
                for _, ref_table, _ in table_def.fk_constraints:
                    graph.add_edge(ref_table, table_def.name)

            # 4. Validate foreign key references (Unresolved dependencies check)
            graph.validate_dependencies(declared_tables)

            # 5. Resolve topological ordering and parallel execution groups (Kahn's algorithm)
            ordered_tables, execution_groups, dependency_levels = (
                graph.get_topological_sort_and_layers()
            )

            # 6. Extract warnings from validation report & planner context
            warnings: list[str] = []
            if validation_report.warnings:
                warnings.extend(validation_report.warnings)

            # Check if any tables were not parsed due to semantic errors in validator
            if len(ordered_tables) < len(parsed_tables):
                warnings.append(
                    "Some tables in the DDL could not be mapped to the execution plan."
                )

            # 7. Compute heuristics (complexity, resources, costs, and statistics)
            table_count = len(ordered_tables)
            total_dependencies = sum(
                len(t.fk_constraints) for t in parsed_tables.values()
            )

            # Row targets logic: default to 100 if not specified
            targets = row_targets or {}
            default_target = 100
            table_row_targets = {
                t: targets.get(t, targets.get(t.lower(), default_target))
                for t in ordered_tables
            }
            total_row_target = sum(table_row_targets.values())

            # Columns count and Nullable ratio calculations
            total_columns, nullable_ratio = self._analyze_ddl_columns(schema_ddl)

            # Compute isolated tables (degree in == 0 and out == 0)
            isolated_tables = sorted(
                [
                    node
                    for node in graph.nodes
                    if graph.in_degree[node] == 0 and len(graph.adj[node]) == 0
                ]
            )

            # Calculate parallel execution duration per layer
            # Heuristic model: 0.1s base per layer + max(0.01s * row_target) in that layer
            estimated_duration = 0.5  # base setup time
            for group in execution_groups:
                group_duration = max(0.1 + 0.01 * table_row_targets[t] for t in group)
                estimated_duration += group_duration
            estimated_duration = round(estimated_duration, 2)

            # CPU Weight (0.1 per table + column weight + relation weight)
            cpu_weight = (
                0.1 * table_count
                + 0.05 * (total_columns / 10.0)
                + 0.05 * total_dependencies
            )
            cpu_weight = max(0.1, min(10.0, round(cpu_weight, 2)))

            # IO Weight (0.05 * row target scale + 0.02 * columns)
            io_weight = 0.05 * (total_row_target / 100.0) + 0.02 * total_columns
            io_weight = max(0.1, min(100.0, round(io_weight, 2)))

            # Memory consumption (Base 16MB + table rows / columns weighting)
            avg_cols = (total_columns / table_count) if table_count > 0 else 5.0
            estimated_memory = 16.0
            for t in ordered_tables:
                row_target = table_row_targets[t]
                estimated_memory += 0.5 * (row_target / 100.0) * (avg_cols / 5.0)
            estimated_memory = round(max(16.0, estimated_memory), 2)

            # Peak memory (base 32MB + memory of the largest parallel execution group)
            peak_group_mem = 0.0
            for group in execution_groups:
                group_mem = sum(
                    0.5 * (table_row_targets[t] / 100.0) * (avg_cols / 5.0)
                    for t in group
                )
                if group_mem > peak_group_mem:
                    peak_group_mem = group_mem
            peak_memory = round(32.0 + peak_group_mem, 2)

            # Complexity Score
            complexity_score = (
                table_count * 1.5
                + total_dependencies * 2.0
                + len(execution_groups) * 3.0
                + (1.0 - nullable_ratio) * 5.0
            )
            complexity_score = round(max(1.0, complexity_score), 2)

            if complexity_score < 15.0:
                complexity_level = "low"
            elif complexity_score < 35.0:
                complexity_level = "medium"
            else:
                complexity_level = "high"

            # Parallelism degree (max group size)
            parallelism = (
                max(len(group) for group in execution_groups) if execution_groups else 1
            )
            parallel_workers = min(parallelism, 8)

            # LLM Heuristics
            llm_calls = table_count
            llm_cost = round(llm_calls * 0.005, 4)
            generation_cost = round(llm_cost + (estimated_duration * 0.0002), 4)

            # Confidence
            confidence = 1.0
            if nullable_ratio < 0.5:
                confidence -= 0.1
            if warnings:
                confidence -= 0.1 * min(len(warnings), 5)
            confidence = max(0.1, min(1.0, round(confidence, 2)))

            cost_estimate = ExecutionCostEstimate(
                estimated_duration_seconds=estimated_duration,
                estimated_memory_mb=estimated_memory,
                estimated_cpu_weight=cpu_weight,
                estimated_io_weight=io_weight,
                estimated_complexity_score=complexity_score,
                estimated_parallelism=parallelism,
                estimated_llm_calls=llm_calls,
                estimated_llm_cost=llm_cost,
                confidence=confidence,
            )

            statistics = PlanningStatistics(
                table_count=table_count,
                relationship_count=total_dependencies,
                dependency_depth=len(execution_groups),
                execution_groups=len(execution_groups),
                independent_groups=len(execution_groups[0]) if execution_groups else 0,
                cyclic_dependencies_detected=False,
                isolated_tables=isolated_tables,
            )

            plan_result = ExecutionPlan(
                execution_id=execution_id,
                schema_hash=schema_hash,
                execution_groups=execution_groups,
                ordered_tables=ordered_tables,
                dependency_levels=dependency_levels,
                estimated_complexity=complexity_level,
                estimated_execution_time=estimated_duration,
                warnings=warnings,
                planner_version=self.version,
                generated_at=datetime.now(UTC).isoformat(),
                estimated_total_duration=estimated_duration,
                estimated_peak_memory=peak_memory,
                estimated_parallel_workers=parallel_workers,
                estimated_llm_cost=llm_cost,
                estimated_generation_cost=generation_cost,
                planning_confidence=confidence,
                cost_estimate=cost_estimate,
                statistics=statistics,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000.0

            logger.info(
                EventID.LOG_INFO,
                "Guardian Planner completed successfully",
                component="GuardianPlanner",
                execution_id=execution_id,
                schema_hash=schema_hash,
                latency_ms=round(latency_ms, 2),
                ordered_tables_count=table_count,
                estimated_total_duration=estimated_duration,
                estimated_peak_memory=peak_memory,
                estimated_parallel_workers=parallel_workers,
                estimated_llm_cost=llm_cost,
                estimated_generation_cost=generation_cost,
                planning_complexity=complexity_level,
                parallelism=parallelism,
            )

            return plan_result

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            error_msg = str(exc)

            logger.error(
                EventID.LOG_ERROR,
                f"Guardian Planner execution failed: {error_msg}",
                component="GuardianPlanner",
                execution_id=execution_id,
                schema_hash=schema_hash,
                latency_ms=round(latency_ms, 2),
                error_class=type(exc).__name__,
            )

            if isinstance(exc, GuardianPlannerException):
                raise
            raise GuardianPlannerException(f"Planning failed: {error_msg}") from exc

    def _analyze_ddl_columns(self, schema_ddl: str) -> tuple[int, float]:
        """Parse DDL to count columns and determine nullable ratio."""
        # Clean comments
        cleaned = re.sub(r"--.*", "", schema_ddl)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

        total_cols = 0
        nullable_cols = 0

        pos = 0
        while True:
            match = re.search(
                r"\bCREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
                cleaned[pos:],
                re.IGNORECASE,
            )
            if not match:
                break

            tbl_start_idx = pos + match.start()
            paren_start = cleaned.find("(", tbl_start_idx + match.end() - match.start())
            if paren_start == -1:
                pos = tbl_start_idx + match.end()
                continue

            # Find matching paren
            paren_depth = 1
            idx = paren_start + 1
            while idx < len(cleaned) and paren_depth > 0:
                char = cleaned[idx]
                if char == "(":
                    paren_depth += 1
                elif char == ")":
                    paren_depth -= 1
                idx += 1

            if paren_depth > 0:
                pos = idx
                continue

            body = cleaned[paren_start + 1 : idx - 1].strip()
            lines = []
            curr_line: list[str] = []
            depth = 0
            for char in body:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                if char == "," and depth == 0:
                    lines.append("".join(curr_line).strip())
                    curr_line = []
                else:
                    curr_line.append(char)
            if curr_line:
                lines.append("".join(curr_line).strip())

            for line in lines:
                if not line:
                    continue
                if re.match(
                    r"^(PRIMARY\s+KEY|FOREIGN\s+KEY|CONSTRAINT|UNIQUE|INDEX|KEY)\b",
                    line,
                    re.IGNORECASE,
                ):
                    continue

                # Column definition
                col_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+(.*)", line)
                if col_match:
                    total_cols += 1
                    col_rest = col_match.group(2).upper()
                    is_pk = "PRIMARY KEY" in col_rest
                    is_not_null = "NOT NULL" in col_rest

                    if is_not_null or is_pk:
                        pass
                    else:
                        nullable_cols += 1

            pos = idx

        nullable_ratio = (nullable_cols / total_cols) if total_cols > 0 else 0.0
        return total_cols, nullable_ratio
