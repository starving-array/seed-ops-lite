"""Unit tests for the Workflow Execution Planner."""

from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
    WorkflowDefinition,
    WorkflowExecutionPlanner,
)


def test_planner_linear_workflow() -> None:
    """Verify topological stage numbering on a simple linear workflow."""
    step1 = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-2", name="Step 2", type=DSLStepType.GENERATION, depends_on=["step-1"]
    )
    step3 = StepDefinition(
        id="step-3", name="Step 3", type=DSLStepType.VALIDATION, depends_on=["step-2"]
    )
    workflow = WorkflowDefinition(
        id="wf-linear",
        name="Linear Flow",
        steps=[step1, step2, step3],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)
    assert plan.statistics.total_steps == 3
    assert plan.statistics.root_steps == 1
    assert plan.statistics.leaf_steps == 1
    assert plan.statistics.parallel_stages == 3
    assert plan.statistics.maximum_parallelism == 1
    assert plan.critical_path == ["step-1", "step-2", "step-3"]
    assert plan.nodes["step-1"].stage_number == 1
    assert plan.nodes["step-2"].stage_number == 2
    assert plan.nodes["step-3"].stage_number == 3


def test_planner_parallel_workflow() -> None:
    """Verify parallel groupings for steps with no mutual dependencies."""
    step1 = StepDefinition(id="step-1", name="Root", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-2", name="Branch 1", type=DSLStepType.GENERATION, depends_on=["step-1"]
    )
    step3 = StepDefinition(
        id="step-3", name="Branch 2", type=DSLStepType.GENERATION, depends_on=["step-1"]
    )
    step4 = StepDefinition(
        id="step-4", name="Branch 3", type=DSLStepType.GENERATION, depends_on=["step-1"]
    )
    step5 = StepDefinition(
        id="step-5",
        name="Leaf",
        type=DSLStepType.VALIDATION,
        depends_on=["step-2", "step-3", "step-4"],
    )
    workflow = WorkflowDefinition(
        id="wf-parallel",
        name="Parallel Flow",
        steps=[step1, step2, step3, step4, step5],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)
    assert plan.statistics.total_steps == 5
    assert plan.statistics.parallel_stages == 3
    assert plan.statistics.maximum_parallelism == 3  # step-2, step-3, step-4 in stage 2
    assert plan.stages[1].stage_number == 2
    assert set(plan.stages[1].steps) == {"step-2", "step-3", "step-4"}
    assert plan.statistics.critical_path_length == 3  # step-1 -> any branch -> step-5
    assert len(plan.critical_path) == 3


def test_planner_multiple_roots_and_leaves() -> None:
    """Verify statistics calculation with multiple roots and leaf steps."""
    step1 = StepDefinition(id="step-1", name="Root 1", type=DSLStepType.PROMPT)
    step2 = StepDefinition(id="step-2", name="Root 2", type=DSLStepType.PROMPT)
    step3 = StepDefinition(
        id="step-3",
        name="Leaf 1",
        type=DSLStepType.EXPORT,
        depends_on=["step-1", "step-2"],
    )
    step4 = StepDefinition(
        id="step-4", name="Leaf 2", type=DSLStepType.EXPORT, depends_on=["step-2"]
    )
    workflow = WorkflowDefinition(
        id="wf-roots-leaves",
        name="Multi Roots Leaves",
        steps=[step1, step2, step3, step4],
    )

    plan = WorkflowExecutionPlanner.plan(workflow)
    assert plan.statistics.root_steps == 2
    assert plan.statistics.leaf_steps == 2
    assert plan.statistics.parallel_stages == 2
    assert plan.statistics.maximum_parallelism == 2
    assert plan.statistics.dependency_count == 3  # (1->3), (2->3), (2->4)
