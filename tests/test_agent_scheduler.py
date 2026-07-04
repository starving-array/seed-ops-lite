"""Unit and integration tests verifying Agent Execution Scheduler and Dependency Resolution."""

import pytest

from app.agents.execution.scheduler import (
    ExecutionScheduler,
    ReadyQueue,
    SchedulerValidationError,
)
from app.agents.planning.engine import PlanningEngine
from app.agents.planning.models import PlanningContext, PlanningPolicy, PlanningRequest


@pytest.fixture
def planning_context() -> PlanningContext:
    return PlanningContext(
        workflow_id="wf-sched-test",
        execution_id="exec-sched-test",
        agent_id="agent-sched-test",
        system_capabilities=["db_write", "file_read"],
        available_tools=["query-db"],
    )


def test_sequential_scheduling(planning_context: PlanningContext) -> None:
    """Verify standard sequential dependency chains compile to corresponding sequential stages."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Parse inputs, transform data, and export results.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )
    response = engine.generate_plan(req)
    assert response.success is True
    plan = response.plan
    assert plan is not None

    # Schedule
    result = ExecutionScheduler.create_schedule(plan)
    assert len(result.stages) == 3
    assert result.stages[0] == ["task-parse"]
    assert result.stages[1] == ["task-transform"]
    assert result.stages[2] == ["task-export"]

    stats = result.statistics
    assert stats.total_tasks == 3
    assert stats.stage_count == 3
    assert stats.max_parallel_tasks == 1


def test_parallel_scheduling(planning_context: PlanningContext) -> None:
    """Verify parallel branches are grouped together in stages."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Run task branch A and branch B in parallel.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )
    response = engine.generate_plan(req)
    assert response.success is True
    plan = response.plan
    assert plan is not None

    result = ExecutionScheduler.create_schedule(plan)
    assert len(result.stages) == 3  # Start -> Parallel (A, B) -> End
    assert result.stages[0] == ["task-start"]
    assert set(result.stages[1]) == {"task-branch-a", "task-branch-b"}
    assert result.stages[2] == ["task-end"]

    assert result.statistics.max_parallel_tasks == 2


def test_circular_dependency_detection(planning_context: PlanningContext) -> None:
    """Verify circular dependency cycles are caught by validation rules."""
    engine = PlanningEngine()
    req = PlanningRequest(
        goal="Intentionally produce a circular loop.",
        context=planning_context,
        policy=PlanningPolicy.BALANCED,
    )
    # The PlanningEngine returns success=False for circular goal requests because
    # PlanValidator has cycle checks, so we manually instantiate a plan with a cycle.
    response = engine.generate_plan(req)
    assert response.success is False

    # Force mock execution plan generation bypassing validation to verify scheduler cycle checking
    from app.agents.planning.models import ExecutionPlan, TaskEdge, TaskNode

    nodes = {
        "t1": TaskNode(id="t1", title="T1", description="N1"),
        "t2": TaskNode(id="t2", title="T2", description="N2"),
    }
    edges = [TaskEdge(from_id="t1", to_id="t2"), TaskEdge(from_id="t2", to_id="t1")]
    circular_plan = ExecutionPlan(
        id="plan-circ",
        goal="test",
        nodes=nodes,
        edges=edges,
    )

    with pytest.raises(SchedulerValidationError, match="Circular dependency"):
        ExecutionScheduler.create_schedule(circular_plan)


def test_ready_queue_behavior() -> None:
    """Verify pushing ready tasks, completing them, and unblocking downstream tasks."""
    stages = [["task-1"], ["task-2", "task-3"], ["task-4"]]
    deps = {
        "task-1": set(),
        "task-2": {"task-1"},
        "task-3": {"task-1"},
        "task-4": {"task-2", "task-3"},
    }

    queue = ReadyQueue(stages, deps)

    # Initial state: only task-1 has no dependencies satisfied
    ready = queue.get_ready_tasks()
    assert ready == ["task-1"]

    # Schedule task-1
    queue.push_ready("task-1")
    queue.start_task("task-1")
    assert queue.get_ready_tasks() == []

    # Complete task-1 -> unblocks task-2 and task-3
    queue.remove_completed("task-1")
    ready_stage2 = set(queue.get_ready_tasks())
    assert ready_stage2 == {"task-2", "task-3"}

    # Start and complete task-2
    queue.push_ready("task-2")
    queue.start_task("task-2")
    queue.remove_completed("task-2")
    # task-4 remains blocked because task-3 is not completed yet
    assert queue.get_ready_tasks() == ["task-3"]

    # Start and complete task-3 -> unblocks task-4
    queue.push_ready("task-3")
    queue.start_task("task-3")
    queue.remove_completed("task-3")
    assert queue.get_ready_tasks() == ["task-4"]

    # Complete task-4 -> queue registers full graph completion
    queue.push_ready("task-4")
    queue.start_task("task-4")
    queue.remove_completed("task-4")
    assert queue.detect_completion() is True
