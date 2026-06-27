"""Unit tests for the Guardian Planner validating graph construction, sorting, cycle detection, and cost estimation."""

import pytest

from app.agents.guardian import (
    DependencyCycleError,
    DependencyGraph,
    GuardianPlanner,
    GuardianPlannerException,
    UnresolvedDependencyError,
)
from app.agents.schema_validation.models import SchemaValidationReport


def test_dependency_graph_sorting() -> None:
    """Verify that DependencyGraph topological sorting is deterministic and correct."""
    graph = DependencyGraph()
    # Construct nodes
    graph.add_node("c")
    graph.add_node("b")
    graph.add_node("a")

    # Add edges: a depends on b (b -> a), b depends on c (c -> b)
    # c must be seeded first, then b, then a
    graph.add_edge("c", "b")
    graph.add_edge("b", "a")

    ordered, groups, levels = graph.get_topological_sort_and_layers()
    assert ordered == ["c", "b", "a"]
    assert groups == [["c"], ["b"], ["a"]]
    assert levels == {"c": 0, "b": 1, "a": 2}


def test_dependency_graph_sorting_determinism() -> None:
    """Verify independent tables are sorted alphabetically in topological sort layers."""
    graph = DependencyGraph()
    # Add multiple independent tables
    graph.add_node("z")
    graph.add_node("y")
    graph.add_node("x")

    ordered, groups, levels = graph.get_topological_sort_and_layers()
    # Should resolve alphabetically: x, y, z
    assert ordered == ["x", "y", "z"]
    assert groups == [["x", "y", "z"]]
    assert levels == {"x": 0, "y": 0, "z": 0}


def test_dependency_graph_cycle_detection() -> None:
    """Verify that a cycle in DependencyGraph raises a DependencyCycleError."""
    graph = DependencyGraph()
    # Add a loop: a -> b -> a
    graph.add_edge("a", "b")
    graph.add_edge("b", "a")

    with pytest.raises(DependencyCycleError) as exc:
        graph.get_topological_sort_and_layers()
    assert "Dependency cycle detected" in str(exc.value)


@pytest.mark.asyncio
async def test_planner_success() -> None:
    """Test successful plan generation from SQL schema DDL including cost estimation heuristics and statistics."""
    schema_ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(50) NOT NULL
    );

    CREATE TABLE posts (
        id INT PRIMARY KEY,
        user_id INT,
        title VARCHAR(100) NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );

    CREATE TABLE comments (
        id INT PRIMARY KEY,
        post_id INT,
        body TEXT,
        FOREIGN KEY (post_id) REFERENCES posts (id)
    );

    CREATE TABLE logs (
        id INT PRIMARY KEY,
        action VARCHAR(100)
    );
    """
    report = SchemaValidationReport(
        overall_status="pass",
        summary="Schema is valid",
        findings=[],
        recommendations=[],
        warnings=["Report warning"],
        execution_statistics={},
        executed_skills=["structure", "relationships"],
        execution_duration_ms=10.0,
    )

    planner = GuardianPlanner()
    plan = await planner.plan(schema_ddl, report)

    # 1. Verification of basic fields
    assert plan.execution_id is not None
    assert plan.schema_hash is not None
    assert plan.ordered_tables == ["logs", "users", "posts", "comments"]
    assert plan.execution_groups == [["logs", "users"], ["posts"], ["comments"]]
    assert plan.dependency_levels == {"logs": 0, "users": 0, "posts": 1, "comments": 2}
    assert plan.estimated_complexity in ("low", "medium", "high")
    assert plan.estimated_execution_time > 0.0
    assert "Report warning" in plan.warnings

    # 2. Verification of extended metadata
    assert plan.estimated_total_duration > 0.0
    assert plan.estimated_peak_memory >= 32.0
    assert plan.estimated_parallel_workers == 2  # max group is logs, users (size 2)
    assert plan.estimated_llm_cost > 0.0
    assert plan.estimated_generation_cost > 0.0
    assert 0.0 <= plan.planning_confidence <= 1.0

    # 3. Verification of PlanningStatistics
    assert plan.statistics.table_count == 4
    assert plan.statistics.relationship_count == 2
    assert plan.statistics.dependency_depth == 3
    assert plan.statistics.execution_groups == 3
    assert plan.statistics.independent_groups == 2
    assert plan.statistics.cyclic_dependencies_detected is False
    assert plan.statistics.isolated_tables == ["logs"]  # logs has no relations

    # 4. Verification of ExecutionCostEstimate
    assert (
        plan.cost_estimate.estimated_duration_seconds == plan.estimated_total_duration
    )
    assert plan.cost_estimate.estimated_memory_mb > 0.0
    assert plan.cost_estimate.estimated_cpu_weight > 0.0
    assert plan.cost_estimate.estimated_io_weight > 0.0
    assert plan.cost_estimate.estimated_complexity_score > 0.0
    assert plan.cost_estimate.estimated_parallelism == 2
    assert plan.cost_estimate.estimated_llm_calls == 4
    assert plan.cost_estimate.estimated_llm_cost == plan.estimated_llm_cost
    assert plan.cost_estimate.confidence == plan.planning_confidence


@pytest.mark.asyncio
async def test_planner_with_custom_row_targets() -> None:
    """Verify that passing custom row targets scales estimated costs, memory, and duration deterministically."""
    schema_ddl = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(50)
    );
    """
    report = SchemaValidationReport(
        overall_status="pass",
        summary="Schema is valid",
        findings=[],
        recommendations=[],
        warnings=[],
        execution_statistics={},
        executed_skills=["structure"],
        execution_duration_ms=1.0,
    )

    planner = GuardianPlanner()

    # Plan A: Default targets (100 rows)
    plan_default = await planner.plan(schema_ddl, report)

    # Plan B: Large custom target (5000 rows)
    plan_large = await planner.plan(schema_ddl, report, row_targets={"users": 5000})

    # Memory and duration should scale up deterministically
    assert plan_large.estimated_total_duration > plan_default.estimated_total_duration
    assert (
        plan_large.cost_estimate.estimated_memory_mb
        > plan_default.cost_estimate.estimated_memory_mb
    )
    assert plan_large.estimated_peak_memory > plan_default.estimated_peak_memory


@pytest.mark.asyncio
async def test_planner_failed_validation_report_raises() -> None:
    """Verify that a validation report with status 'fail' raises a GuardianPlannerException."""
    report = SchemaValidationReport(
        overall_status="fail",
        summary="Schema contains critical SQL keywords and syntax errors.",
        findings=[],
        recommendations=[],
        warnings=[],
        execution_statistics={},
        executed_skills=["structure"],
        execution_duration_ms=5.0,
    )
    planner = GuardianPlanner()
    with pytest.raises(GuardianPlannerException) as exc:
        await planner.plan("CREATE TABLE t1 (id INT PRIMARY KEY);", report)
    assert "Schema validation failed" in str(exc.value)


@pytest.mark.asyncio
async def test_planner_cycle_raises() -> None:
    """Verify that cyclic DDL references raise a DependencyCycleError."""
    schema_ddl = """
    CREATE TABLE t1 (
        id INT PRIMARY KEY,
        t2_id INT,
        FOREIGN KEY (t2_id) REFERENCES t2 (id)
    );
    CREATE TABLE t2 (
        id INT PRIMARY KEY,
        t1_id INT,
        FOREIGN KEY (t1_id) REFERENCES t1 (id)
    );
    """
    report = SchemaValidationReport(
        overall_status="pass",
        summary="No issues",
        findings=[],
        recommendations=[],
        warnings=[],
        execution_statistics={},
        executed_skills=["relationships"],
        execution_duration_ms=2.0,
    )
    planner = GuardianPlanner()
    with pytest.raises(DependencyCycleError) as exc:
        await planner.plan(schema_ddl, report)
    assert "Dependency cycle detected" in str(exc.value)


@pytest.mark.asyncio
async def test_planner_unresolved_dependency_raises() -> None:
    """Verify that referencing a non-existent table raises an UnresolvedDependencyError."""
    schema_ddl = """
    CREATE TABLE t1 (
        id INT PRIMARY KEY,
        missing_id INT,
        FOREIGN KEY (missing_id) REFERENCES missing_table (id)
    );
    """
    report = SchemaValidationReport(
        overall_status="pass",
        summary="No issues",
        findings=[],
        recommendations=[],
        warnings=[],
        execution_statistics={},
        executed_skills=["relationships"],
        execution_duration_ms=2.0,
    )
    planner = GuardianPlanner()
    with pytest.raises(UnresolvedDependencyError) as exc:
        await planner.plan(schema_ddl, report)
    assert "references undeclared table" in str(exc.value)
