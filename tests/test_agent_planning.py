"""Unit and integration tests verifying the Agent Planning Engine."""

import pytest

from app.agents.planning.engine import PlanningEngine
from app.agents.planning.models import (
    PlanningContext,
    PlanningPolicy,
    PlanningRequest,
    TaskComplexity,
    TaskPriority,
)


@pytest.fixture
def planning_context() -> PlanningContext:
    return PlanningContext(
        workflow_id="wf-plan-test",
        execution_id="exec-plan-test",
        agent_id="agent-plan-test",
        system_capabilities=["db_write", "file_read", "http_call"],
        available_tools=["query-db", "markdown-export"],
    )


def test_sequential_planning(planning_context: PlanningContext) -> None:
    """Verify that a sequential chain of tasks is decomposed, structured, and validated."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Parse inputs, transform data, and export results.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )

    response = engine.generate_plan(req)
    assert response.success is True
    assert response.plan is not None

    plan = response.plan
    assert len(plan.nodes) == 3
    assert "task-parse" in plan.nodes
    assert "task-transform" in plan.nodes
    assert "task-export" in plan.nodes

    # Assert sequential edges (DAG connectivity)
    assert len(plan.edges) == 2
    assert plan.edges[0].from_id == "task-parse"
    assert plan.edges[0].to_id == "task-transform"


def test_parallel_planning(planning_context: PlanningContext) -> None:
    """Verify that goals containing 'parallel' trigger branching subgraphs and TaskGroups."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Run task branch A and branch B in parallel.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )

    response = engine.generate_plan(req)
    assert response.success is True
    assert response.plan is not None

    plan = response.plan
    assert len(plan.nodes) == 4
    assert "task-branch-a" in plan.nodes
    assert "task-branch-b" in plan.nodes

    # Assert TaskGroup is generated
    assert len(plan.groups) == 1
    assert plan.groups[0].id == "grp-parallel"
    assert "task-branch-a" in plan.groups[0].task_ids


def test_conditional_branches(planning_context: PlanningContext) -> None:
    """Verify branching structures are compiled with loop and conditional attributes."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Execute a conditional check on status.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )

    response = engine.generate_plan(req)
    assert response.success is True
    plan = response.plan
    assert plan is not None

    cond_node = plan.nodes["task-cond"]
    assert cond_node.is_conditional is True
    assert cond_node.condition_expression == "$.status == 'ok'"


def test_loop_structures(planning_context: PlanningContext) -> None:
    """Verify loop markers are generated with correct bounds expressions."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Process entries using a loop until empty.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )

    response = engine.generate_plan(req)
    assert response.success is True
    plan = response.plan
    assert plan is not None

    loop_node = plan.nodes["task-loop"]
    assert loop_node.is_loop is True
    assert loop_node.loop_expression == "count < 5"


def test_cycle_detection(planning_context: PlanningContext) -> None:
    """Verify cycle detection identifies circular dependencies and fails validation."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Intentionally produce a circular loop.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )

    response = engine.generate_plan(req)
    assert response.success is False
    assert any("circular" in e.lower() or "cycle" in e.lower() for e in response.errors)


def test_policy_assignments(planning_context: PlanningContext) -> None:
    """Verify planning policies properly skew task priorities and complexities."""
    engine = PlanningEngine()

    # Conservative Policy
    req_cons = PlanningRequest(
        goal="Decompose steps.",
        context=planning_context,
        policy=PlanningPolicy.CONSERVATIVE,
    )
    res_cons = engine.generate_plan(req_cons)
    assert res_cons.success is True
    assert res_cons.plan is not None
    assert res_cons.plan.nodes["task-transform"].priority == TaskPriority.LOW

    # Highest Quality Policy
    req_qual = PlanningRequest(
        goal="Decompose steps.",
        context=planning_context,
        policy=PlanningPolicy.HIGHEST_QUALITY,
    )
    res_qual = engine.generate_plan(req_qual)
    assert res_qual.success is True
    assert res_qual.plan is not None
    assert res_qual.plan.nodes["task-parse"].complexity == TaskComplexity.COMPLEX


def test_validation_failures(planning_context: PlanningContext) -> None:
    """Verify missing capabilities or tools trigger validation failures."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Request missing capability requirements.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )

    response = engine.generate_plan(req)
    assert response.success is False
    assert len(response.errors) > 0
    assert any(
        "capability" in e.lower() or "tool" in e.lower() for e in response.errors
    )


def test_metrics_collection(planning_context: PlanningContext) -> None:
    """Verify statistics gather planning performance timings and error counts."""
    engine = PlanningEngine()

    # Run successful plan
    req_ok = PlanningRequest(
        goal="Sequential run.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )
    engine.generate_plan(req_ok)

    # Run failing plan
    req_fail = PlanningRequest(
        goal="Circular run.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )
    engine.generate_plan(req_fail)

    stats = engine.get_statistics()
    assert stats.plans_created == 1
    assert stats.validation_failures == 1
    assert stats.average_task_count == 3.0
