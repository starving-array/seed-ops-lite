"""Serialization, deserialization, and reference syntax parsing for the Workflow DSL."""

import json
import re
from typing import Any

import yaml  # type: ignore[import-untyped]

from app.workflow.dsl.models import WorkflowDefinition

# Regex pattern to match DSL references:
# 1. ${workflow.var_name}
# 2. ${steps.step_id.output.property}
WORKFLOW_VAR_PATTERN = re.compile(r"^\$\{workflow\.([a-zA-Z0-9_]+)\}$")
STEP_OUTPUT_PATTERN = re.compile(
    r"^\$\{steps\.([a-zA-Z0-9_-]+)\.output(?:\.([a-zA-Z0-9_\.]+))?\}$"
)


def parse_reference(value: Any) -> dict[str, Any] | None:
    """Parses a DSL reference string and returns structured metadata.

    Args:
        value: The string containing the reference to parse.

    Returns:
        A dictionary describing the reference source, keys, and paths,
        or None if the value is not a valid reference string.
    """
    if not isinstance(value, str):
        return None

    value = value.strip()

    # Check workflow variable pattern
    wf_match = WORKFLOW_VAR_PATTERN.match(value)
    if wf_match:
        return {
            "type": "workflow",
            "variable": wf_match.group(1),
        }

    # Check step output pattern
    step_match = STEP_OUTPUT_PATTERN.match(value)
    if step_match:
        step_id = step_match.group(1)
        path_str = step_match.group(2)
        path = path_str.split(".") if path_str else []
        return {
            "type": "step",
            "step_id": step_id,
            "path": path,
        }

    return None


def load_from_json(json_str: str) -> WorkflowDefinition:
    """Deserializes a JSON string into a WorkflowDefinition model.

    Args:
        json_str: The source JSON string.

    Returns:
        A WorkflowDefinition instance.
    """
    data = json.loads(json_str)
    return WorkflowDefinition.model_validate(data)


def load_from_yaml(yaml_str: str) -> WorkflowDefinition:
    """Deserializes a YAML string into a WorkflowDefinition model.

    Args:
        yaml_str: The source YAML string.

    Returns:
        A WorkflowDefinition instance.
    """
    data = yaml.safe_load(yaml_str)
    return WorkflowDefinition.model_validate(data)


def to_json(workflow: WorkflowDefinition, indent: int = 2) -> str:
    """Serializes a WorkflowDefinition model into a JSON string.

    Args:
        workflow: The WorkflowDefinition instance.
        indent: JSON indentation spacing size.

    Returns:
        JSON string representation.
    """
    return workflow.model_dump_json(indent=indent)


def to_yaml(workflow: WorkflowDefinition) -> str:
    """Serializes a WorkflowDefinition model into a YAML string.

    Args:
        workflow: The WorkflowDefinition instance.

    Returns:
        YAML string representation.
    """
    # Dump to JSON-serializable dict first to convert Enums and custom types to string primitives
    data = workflow.model_dump(mode="json", exclude_none=True)
    return str(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
