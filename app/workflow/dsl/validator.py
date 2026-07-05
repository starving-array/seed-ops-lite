"""Validation engine for structural and logical correctness of Workflow DSL."""

from typing import Any

from app.workflow.dsl.models import VariableType, WorkflowDefinition
from app.workflow.dsl.parser import parse_reference


def validate_workflow(workflow: WorkflowDefinition) -> list[str]:
    """Runs structural, type, dependency, and loop checks on a WorkflowDefinition.

    Args:
        workflow: The workflow definition to check.

    Returns:
        A list of validation error strings. If empty, validation passed successfully.
    """
    errors: list[str] = []

    # 1. Unique step IDs
    step_ids = set()
    for step in workflow.steps:
        if step.id in step_ids:
            errors.append(f"Duplicate step ID detected: '{step.id}'")
        step_ids.add(step.id)

    # 2. Missing dependencies
    for step in workflow.steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                errors.append(f"Step '{step.id}' depends on missing step ID: '{dep}'")

    # 3. Variable type validation
    for var_name, var_def in workflow.variables.items():
        if var_def.default is not None:
            val = var_def.default
            v_type = var_def.type
            if v_type == VariableType.STRING and not isinstance(val, str):
                errors.append(
                    f"Variable '{var_name}' default value '{val}' is not of type string."
                )
            elif v_type == VariableType.INTEGER:
                if not isinstance(val, int) or isinstance(val, bool):
                    errors.append(
                        f"Variable '{var_name}' default value '{val}' is not of type integer."
                    )
            elif v_type == VariableType.FLOAT:
                if not isinstance(val, int | float) or isinstance(val, bool):
                    errors.append(
                        f"Variable '{var_name}' default value '{val}' is not of type float."
                    )
            elif v_type == VariableType.BOOLEAN and not isinstance(val, bool):
                errors.append(
                    f"Variable '{var_name}' default value '{val}' is not of type boolean."
                )
            elif v_type == VariableType.LIST and not isinstance(val, list):
                errors.append(
                    f"Variable '{var_name}' default value '{val}' is not of type list."
                )
            elif v_type == VariableType.OBJECT and not isinstance(val, dict):
                errors.append(
                    f"Variable '{var_name}' default value '{val}' is not of type object."
                )

    # 4. Cyclic references (DAG loop check)
    has_cycle, cycle_err = _detect_cycles(workflow)
    if has_cycle:
        errors.append(cycle_err)

    # 5. Invalid input mapping references
    for step in workflow.steps:
        # Traverse input mapping recursively to find all reference strings
        _validate_input_mapping(step.id, step.input, workflow, step_ids, errors)

    return errors


def _detect_cycles(workflow: WorkflowDefinition) -> tuple[bool, str]:
    """Detects cycles in the dependency graph of steps.

    Returns:
        (has_cycle, error_message)
    """
    # Build graph: step_id -> list of steps that depend on it
    adj: dict[str, list[str]] = {step.id: [] for step in workflow.steps}
    in_degree: dict[str, int] = {step.id: 0 for step in workflow.steps}

    for step in workflow.steps:
        for dep in step.depends_on:
            if dep in adj:
                adj[dep].append(step.id)
                in_degree[step.id] += 1

    # Queue of nodes with in-degree 0
    queue = [node for node, deg in in_degree.items() if deg == 0]
    visited_count = 0

    while queue:
        node = queue.pop(0)
        visited_count += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count != len(workflow.steps):
        return True, "Cyclic dependency loop detected within workflow steps."

    return False, ""


def _validate_input_mapping(
    step_id: str,
    mapping: Any,
    workflow: WorkflowDefinition,
    step_ids: set[str],
    errors: list[str],
) -> None:
    """Recursively parses and validates all inputs and mappings."""
    if isinstance(mapping, dict):
        for v in mapping.values():
            _validate_input_mapping(step_id, v, workflow, step_ids, errors)
    elif isinstance(mapping, list):
        for item in mapping:
            _validate_input_mapping(step_id, item, workflow, step_ids, errors)
    elif isinstance(mapping, str):
        ref = parse_reference(mapping)
        if ref is not None:
            if ref["type"] == "workflow":
                var_name = ref["variable"]
                if var_name not in workflow.variables:
                    errors.append(
                        f"Step '{step_id}' references missing workflow variable: '{var_name}'"
                    )
            elif ref["type"] == "step":
                ref_step_id = ref["step_id"]
                if ref_step_id not in step_ids:
                    errors.append(
                        f"Step '{step_id}' references missing step ID: '{ref_step_id}'"
                    )
