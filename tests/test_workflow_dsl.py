"""Unit tests for the Workflow Definition Language (DSL) parser and validator."""

from app.workflow.dsl import (
    DSLStepType,
    StepDefinition,
    VariableDefinition,
    VariableType,
    WorkflowDefinition,
    load_from_json,
    load_from_yaml,
    parse_reference,
    to_json,
    to_yaml,
    validate_workflow,
)


def test_reference_parser() -> None:
    """Verify parsing workflow variable and step output reference strings."""
    # Workflow var
    ref_wf = parse_reference("${workflow.customer_name}")
    assert ref_wf is not None
    assert ref_wf["type"] == "workflow"
    assert ref_wf["variable"] == "customer_name"

    # Step output
    ref_step = parse_reference("${steps.gen_schema.output.sql_path}")
    assert ref_step is not None
    assert ref_step["type"] == "step"
    assert ref_step["step_id"] == "gen_schema"
    assert ref_step["path"] == ["sql_path"]

    # Step output without path
    ref_step_no_path = parse_reference("${steps.gen_schema.output}")
    assert ref_step_no_path is not None
    assert ref_step_no_path["type"] == "step"
    assert ref_step_no_path["step_id"] == "gen_schema"
    assert ref_step_no_path["path"] == []

    # Invalid
    assert parse_reference("literal_value") is None
    assert parse_reference("${invalid_format}") is None


def test_workflow_dsl_creation_and_validation() -> None:
    """Verify clean workflow validation is successful."""
    var_def = VariableDefinition(type=VariableType.STRING, default="John Doe")
    step_def_1 = StepDefinition(
        id="step-1",
        name="Generate Data",
        type=DSLStepType.GENERATION,
        input={"user": "${workflow.author_name}"},
    )
    step_def_2 = StepDefinition(
        id="step-2",
        name="Validate Schema",
        type=DSLStepType.VALIDATION,
        depends_on=["step-1"],
        input={"source_path": "${steps.step-1.output.file_path}"},
    )
    workflow = WorkflowDefinition(
        id="wf-test-1",
        name="Test Workflow Pipeline",
        variables={"author_name": var_def},
        steps=[step_def_1, step_def_2],
    )

    errors = validate_workflow(workflow)
    assert len(errors) == 0


def test_workflow_dsl_validation_errors() -> None:
    """Verify validation flags errors for missing deps, duplicate steps, and type mismatches."""
    # Duplicate step IDs & Missing dependencies
    workflow_bad = WorkflowDefinition(
        id="wf-test-bad",
        name="Bad Workflow",
        steps=[
            StepDefinition(id="step-1", name="Step 1", type=DSLStepType.PROMPT),
            StepDefinition(
                id="step-1", name="Step 1 Duplicate", type=DSLStepType.VALIDATION
            ),
            StepDefinition(
                id="step-2",
                name="Step 2",
                type=DSLStepType.GENERATION,
                depends_on=["missing-step"],
            ),
        ],
    )
    errors = validate_workflow(workflow_bad)
    assert any("Duplicate step ID" in err for err in errors)
    assert any("depends on missing step ID" in err for err in errors)

    # Invalid variable types
    workflow_bad_var = WorkflowDefinition(
        id="wf-bad-var",
        name="Bad Var",
        variables={
            "max_runs": VariableDefinition(
                type=VariableType.INTEGER, default="not_an_int"
            )
        },
    )
    errors = validate_workflow(workflow_bad_var)
    assert any("is not of type integer" in err for err in errors)


def test_dependency_cycle_detection() -> None:
    """Verify cyclic dependency checking flags execution loops."""
    step1 = StepDefinition(
        id="step-1", name="Step 1", type=DSLStepType.PROMPT, depends_on=["step-2"]
    )
    step2 = StepDefinition(
        id="step-2", name="Step 2", type=DSLStepType.PROMPT, depends_on=["step-1"]
    )
    workflow = WorkflowDefinition(
        id="wf-cyclic",
        name="Cyclic Workflow",
        steps=[step1, step2],
    )
    errors = validate_workflow(workflow)
    assert any("Cyclic dependency loop detected" in err for err in errors)


def test_json_serialization_round_trip() -> None:
    """Verify JSON marshalling and unmarshalling preserves fields."""
    step = StepDefinition(
        id="step-1",
        name="Step 1",
        type=DSLStepType.PROMPT,
        input={"test": "val"},
    )
    workflow = WorkflowDefinition(
        id="wf-json",
        name="JSON Workflow",
        steps=[step],
    )

    json_str = to_json(workflow)
    loaded = load_from_json(json_str)

    assert loaded.id == workflow.id
    assert loaded.name == workflow.name
    assert loaded.steps[0].name == "Step 1"
    assert loaded.steps[0].input["test"] == "val"


def test_yaml_serialization_round_trip() -> None:
    """Verify YAML marshalling and unmarshalling preserves fields."""
    step = StepDefinition(
        id="step-1",
        name="Step 1",
        type=DSLStepType.DELAY,
        input={"duration": 10},
    )
    workflow = WorkflowDefinition(
        id="wf-yaml",
        name="YAML Workflow",
        steps=[step],
    )

    yaml_str = to_yaml(workflow)
    loaded = load_from_yaml(yaml_str)

    assert loaded.id == workflow.id
    assert loaded.name == workflow.name
    assert loaded.steps[0].name == "Step 1"
    assert loaded.steps[0].input["duration"] == 10
