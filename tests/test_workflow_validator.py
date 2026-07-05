"""Unit tests for the Workflow Validation Engine."""

from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
    VariableDefinition,
    VariableType,
    WorkflowDefinition,
)
from app.workflow.dsl.validator_engine import (
    ValidationCode,
    WorkflowValidator,
)


def test_validator_valid_workflow() -> None:
    """Verify that a correct workflow configuration passes validation with zero issues."""
    step1 = StepDefinition(
        id="step-1",
        name="Generate Data",
        type=DSLStepType.GENERATION,
        input={"prompt_flavor": "${workflow.flavor}"},
        output={"out_path": "string"},
    )
    step2 = StepDefinition(
        id="step-2",
        name="Validate Output",
        type=DSLStepType.VALIDATION,
        depends_on=["step-1"],
        input={"check_path": "${steps.step-1.output.out_path}"},
    )
    workflow = WorkflowDefinition(
        id="wf-valid",
        name="Valid Pipeline",
        description="Audited pipeline definition",
        author="Validator Tests",
        variables={
            "flavor": VariableDefinition(type=VariableType.STRING, default="postgresql")
        },
        steps=[step1, step2],
    )

    result = WorkflowValidator.validate(workflow)
    assert result.valid is True
    assert len(result.errors) == 0
    assert result.statistics.step_count == 2
    assert result.statistics.variable_count == 1
    assert result.statistics.dependency_count == 1
    assert result.statistics.max_graph_depth == 2
    assert result.statistics.root_step_count == 1
    assert result.statistics.leaf_step_count == 1


def test_validator_empty_workflow() -> None:
    """Verify validation detects empty workflows."""
    workflow = WorkflowDefinition(
        id="wf-empty",
        name="Empty Pipeline",
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(i.code == ValidationCode.EMPTY_WORKFLOW for i in result.errors)
    assert result.statistics.step_count == 0


def test_validator_duplicate_ids() -> None:
    """Verify validation detects duplicate step IDs."""
    step1 = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-1", name="Step 2 Duplicate", type=DSLStepType.VALIDATION
    )
    workflow = WorkflowDefinition(
        id="wf-dup",
        name="Duplicate IDs",
        steps=[step1, step2],
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(i.code == ValidationCode.DUPLICATE_STEP_ID for i in result.errors)


def test_validator_missing_dependency() -> None:
    """Verify validation flags missing dependencies."""
    step1 = StepDefinition(
        id="step-1",
        name="Step 1",
        type=DSLStepType.PROMPT,
        depends_on=["missing-dependency-step"],
    )
    workflow = WorkflowDefinition(
        id="wf-missing-dep",
        name="Missing Dep",
        steps=[step1],
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(i.code == ValidationCode.MISSING_DEPENDENCY for i in result.errors)


def test_validator_circular_dependency() -> None:
    """Verify circular dependency checking flags loop execution cycles."""
    step1 = StepDefinition(
        id="step-1", name="Step 1", type=DSLStepType.PROMPT, depends_on=["step-2"]
    )
    step2 = StepDefinition(
        id="step-2", name="Step 2", type=DSLStepType.PROMPT, depends_on=["step-1"]
    )
    workflow = WorkflowDefinition(
        id="wf-circular",
        name="Circular Loop",
        steps=[step1, step2],
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(i.code == ValidationCode.CIRCULAR_DEPENDENCY for i in result.errors)
    # Check that unreachable/cycle nodes are logged
    assert any(i.code == ValidationCode.UNREACHABLE_STEP for i in result.errors)


def test_validator_invalid_variable_default() -> None:
    """Verify validation check flags invalid default types."""
    workflow = WorkflowDefinition(
        id="wf-bad-var",
        name="Bad Variable",
        variables={
            "max_retries": VariableDefinition(
                type=VariableType.INTEGER, default="string_val"
            )
        },
        steps=[StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)],
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(i.code == ValidationCode.INVALID_VARIABLE_DEFAULT for i in result.errors)


def test_validator_invalid_references() -> None:
    """Verify validation engine flags invalid mappings and unknown reference paths."""
    step1 = StepDefinition(
        id="step-1",
        name="Step 1",
        type=DSLStepType.PROMPT,
        input={
            "bad_ref": "${workflow.missing_variable}",
            "bad_step_ref": "${steps.missing_step.output.val}",
        },
    )
    workflow = WorkflowDefinition(
        id="wf-bad-refs",
        name="Bad Reference",
        steps=[step1],
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(i.code == ValidationCode.UNKNOWN_VARIABLE_REF for i in result.errors)
    assert any(i.code == ValidationCode.UNKNOWN_STEP_REF for i in result.errors)


def test_validator_missing_producer_dependency() -> None:
    """Verify step input references mapping requires an explicit ancestor link."""
    step1 = StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT)
    step2 = StepDefinition(
        id="step-2",
        name="Step 2",
        type=DSLStepType.VALIDATION,
        # Missing depends_on=["step-1"]
        input={"data": "${steps.step-1.output.payload}"},
    )
    workflow = WorkflowDefinition(
        id="wf-missing-producer",
        name="Missing Producer Link",
        steps=[step1, step2],
    )
    result = WorkflowValidator.validate(workflow)
    assert result.valid is False
    assert any(
        i.code == ValidationCode.MISSING_PRODUCER_DEPENDENCY for i in result.errors
    )


def test_validator_disabled_steps_and_unused_entities() -> None:
    """Verify warnings are generated for disabled steps and unused variables."""
    step1 = StepDefinition(
        id="step-1",
        name="Step 1",
        type=DSLStepType.PROMPT,
        enabled=False,
    )
    workflow = WorkflowDefinition(
        id="wf-warnings",
        name="Warnings Workflow",
        variables={
            "unused_var": VariableDefinition(
                type=VariableType.STRING, default="testing"
            )
        },
        steps=[step1],
    )
    result = WorkflowValidator.validate(workflow)
    # The workflow is technically valid (no errors), but triggers warnings
    assert result.valid is True
    assert len(result.errors) == 0
    assert any(i.code == ValidationCode.DISABLED_STEP for i in result.warnings)
    assert any(i.code == ValidationCode.UNUSED_VARIABLE for i in result.warnings)
