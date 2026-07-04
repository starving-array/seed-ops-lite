"""Comprehensive Workflow Validation Engine."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.workflow.dsl.models import VariableType, WorkflowDefinition
from app.workflow.dsl.parser import parse_reference


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationCode(str, Enum):
    """Structured validation issue error codes."""

    # Workflow structure
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    EMPTY_WORKFLOW = "EMPTY_WORKFLOW"
    MISSING_METADATA = "MISSING_METADATA"

    # Step validation
    DUPLICATE_STEP_ID = "DUPLICATE_STEP_ID"
    MISSING_STEP_NAME = "MISSING_STEP_NAME"
    UNSUPPORTED_STEP_TYPE = "UNSUPPORTED_STEP_TYPE"
    DISABLED_STEP = "DISABLED_STEP"
    INVALID_TIMEOUT = "INVALID_TIMEOUT"
    INVALID_RETRY_COUNT = "INVALID_RETRY_COUNT"

    # Variable validation
    DUPLICATE_VARIABLE = "DUPLICATE_VARIABLE"
    INVALID_VARIABLE_TYPE = "INVALID_VARIABLE_TYPE"
    INVALID_VARIABLE_DEFAULT = "INVALID_VARIABLE_DEFAULT"
    REQUIRED_VARIABLE_CONFLICT = "REQUIRED_VARIABLE_CONFLICT"

    # Dependency / Graph validation
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    DUPLICATE_DEPENDENCY = "DUPLICATE_DEPENDENCY"
    SELF_DEPENDENCY = "SELF_DEPENDENCY"
    CIRCULAR_DEPENDENCY = "CIRCULAR_DEPENDENCY"
    UNREACHABLE_STEP = "UNREACHABLE_STEP"
    ORPHAN_STEP = "ORPHAN_STEP"

    # Reference validation
    UNKNOWN_VARIABLE_REF = "UNKNOWN_VARIABLE_REF"
    UNKNOWN_STEP_REF = "UNKNOWN_STEP_REF"
    INVALID_REF_SYNTAX = "INVALID_REF_SYNTAX"
    MISSING_PRODUCER_DEPENDENCY = "MISSING_PRODUCER_DEPENDENCY"

    # Severities rules warnings/info
    UNUSED_VARIABLE = "UNUSED_VARIABLE"
    UNUSED_OUTPUT = "UNUSED_OUTPUT"
    LONG_TIMEOUT = "LONG_TIMEOUT"
    LARGE_RETRY_COUNT = "LARGE_RETRY_COUNT"


class ValidationIssue(BaseModel):
    """An individual issue detected during workflow validation."""

    model_config = ConfigDict(frozen=True)

    code: ValidationCode = Field(..., description="Unique issue type code.")
    severity: ValidationSeverity = Field(..., description="Severity of the issue.")
    message: str = Field(..., description="Detailed description of the issue.")
    location: str = Field(
        ..., description="String location path in the DSL definition."
    )
    related_entity: str | None = Field(
        default=None, description="The name of the step or variable involved."
    )
    suggested_fix: str = Field(
        ..., description="Actionable recommendation to resolve the issue."
    )


class ValidationStatistics(BaseModel):
    """Aggregated graph and structure metrics for the workflow."""

    model_config = ConfigDict(frozen=True)

    step_count: int = Field(default=0, description="Total number of steps.")
    variable_count: int = Field(default=0, description="Total number of variables.")
    dependency_count: int = Field(default=0, description="Total dependencies declared.")
    max_graph_depth: int = Field(
        default=0, description="Maximum execution path depth (longest path)."
    )
    root_step_count: int = Field(
        default=0, description="Number of root steps (no dependencies)."
    )
    leaf_step_count: int = Field(
        default=0, description="Number of leaf steps (no children)."
    )


class ValidationResult(BaseModel):
    """Result payload of a validation execution run."""

    model_config = ConfigDict(frozen=True)

    valid: bool = Field(..., description="True if no errors were found.")
    errors: list[ValidationIssue] = Field(
        default_factory=list, description="List of ERROR issues."
    )
    warnings: list[ValidationIssue] = Field(
        default_factory=list, description="List of WARNING issues."
    )
    info: list[ValidationIssue] = Field(
        default_factory=list, description="List of INFO issues."
    )
    statistics: ValidationStatistics = Field(
        ..., description="Graph and definition metrics."
    )


class WorkflowValidator:
    """Validator service responsible for auditing WorkflowDefinitions."""

    @staticmethod
    def validate(workflow: WorkflowDefinition) -> ValidationResult:
        """Audits the workflow definition and returns a ValidationResult.

        Args:
            workflow: The workflow definition to validate.

        Returns:
            The ValidationResult detailing issues and statistics.
        """
        issues: list[ValidationIssue] = []

        # Track referenced variables & step outputs
        referenced_vars: set[str] = set()
        referenced_outputs: dict[str, set[str]] = {}

        # 1. Structural checks
        WorkflowValidator._validate_structure(workflow, issues)

        if not workflow.steps:
            # Short-circuit stats and deep checks for empty workflows
            stats = ValidationStatistics()
            errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
            warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
            infos = [i for i in issues if i.severity == ValidationSeverity.INFO]
            return ValidationResult(
                valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                info=infos,
                statistics=stats,
            )

        step_ids = {s.id for s in workflow.steps}

        # 2. Variable check
        WorkflowValidator._validate_variables(workflow, issues)

        # 3. Step validations
        WorkflowValidator._validate_steps(workflow, issues)

        # 4. Dependency checks
        WorkflowValidator._validate_dependencies(workflow, step_ids, issues)

        # 5. Graph analysis & cycle checks
        has_cycle, sorted_steps = WorkflowValidator._validate_dag(
            workflow, step_ids, issues
        )

        # 6. Reference mappings checks (only if no cycle to prevent infinite traversal)
        if not has_cycle:
            WorkflowValidator._validate_mappings(
                workflow, step_ids, referenced_vars, referenced_outputs, issues
            )

        # 7. Unused variable / output alerts
        WorkflowValidator._check_unused_entities(
            workflow, referenced_vars, referenced_outputs, issues
        )

        # 8. Compile statistics
        stats = WorkflowValidator._compile_statistics(workflow, has_cycle)

        # Filter issues by severity
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        infos = [i for i in issues if i.severity == ValidationSeverity.INFO]

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=infos,
            statistics=stats,
        )

    @staticmethod
    def _validate_structure(
        workflow: WorkflowDefinition, issues: list[ValidationIssue]
    ) -> None:
        if not workflow.id:
            issues.append(
                ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    severity=ValidationSeverity.ERROR,
                    message="Workflow definition ID is missing.",
                    location="id",
                    suggested_fix="Define a unique string ID for the workflow.",
                )
            )

        if not workflow.name:
            issues.append(
                ValidationIssue(
                    code=ValidationCode.MISSING_REQUIRED_FIELD,
                    severity=ValidationSeverity.ERROR,
                    message="Workflow name is missing.",
                    location="name",
                    suggested_fix="Define a name for the workflow.",
                )
            )

        if not workflow.steps:
            issues.append(
                ValidationIssue(
                    code=ValidationCode.EMPTY_WORKFLOW,
                    severity=ValidationSeverity.ERROR,
                    message="Workflow contains no steps to execute.",
                    location="steps",
                    suggested_fix="Add at least one execution step to the steps list.",
                )
            )

        if not workflow.description or not workflow.author:
            issues.append(
                ValidationIssue(
                    code=ValidationCode.MISSING_METADATA,
                    severity=ValidationSeverity.WARNING,
                    message="Workflow description or author metadata is missing.",
                    location="metadata",
                    suggested_fix="Provide author and description fields for maintenance audit logging.",
                )
            )

    @staticmethod
    def _validate_variables(
        workflow: WorkflowDefinition, issues: list[ValidationIssue]
    ) -> None:
        for var_name, var_def in workflow.variables.items():
            val = var_def.default
            v_type = var_def.type

            # Conflict: required variables must not have defaults
            if var_def.required and val is not None:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.REQUIRED_VARIABLE_CONFLICT,
                        severity=ValidationSeverity.ERROR,
                        message=f"Variable '{var_name}' is marked required but provides a default value.",
                        location=f"variables.{var_name}",
                        related_entity=var_name,
                        suggested_fix="Remove default value or set required=False.",
                    )
                )

            if val is not None:
                is_valid = True
                if v_type == VariableType.STRING and not isinstance(val, str):
                    is_valid = False
                elif v_type == VariableType.INTEGER:
                    if not isinstance(val, int) or isinstance(val, bool):
                        is_valid = False
                elif v_type == VariableType.FLOAT:
                    if not isinstance(val, int | float) or isinstance(val, bool):
                        is_valid = False
                elif (
                    v_type == VariableType.BOOLEAN
                    and not isinstance(val, bool)
                    or v_type == VariableType.LIST
                    and not isinstance(val, list)
                    or v_type == VariableType.OBJECT
                    and not isinstance(val, dict)
                ):
                    is_valid = False

                if not is_valid:
                    issues.append(
                        ValidationIssue(
                            code=ValidationCode.INVALID_VARIABLE_DEFAULT,
                            severity=ValidationSeverity.ERROR,
                            message=f"Variable '{var_name}' default value '{val}' does not match type '{v_type.value}'.",
                            location=f"variables.{var_name}.default",
                            related_entity=var_name,
                            suggested_fix=f"Change default value to match type '{v_type.value}'.",
                        )
                    )

    @staticmethod
    def _validate_steps(
        workflow: WorkflowDefinition, issues: list[ValidationIssue]
    ) -> None:
        step_ids = []
        for step in workflow.steps:
            if not step.id:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.MISSING_REQUIRED_FIELD,
                        severity=ValidationSeverity.ERROR,
                        message="A step is missing its unique identifier.",
                        location="steps",
                        suggested_fix="Assign a unique id to all steps.",
                    )
                )
            else:
                if step.id in step_ids:
                    issues.append(
                        ValidationIssue(
                            code=ValidationCode.DUPLICATE_STEP_ID,
                            severity=ValidationSeverity.ERROR,
                            message=f"Duplicate step ID '{step.id}' detected.",
                            location=f"steps.{step.id}",
                            related_entity=step.id,
                            suggested_fix="Ensure all step IDs are unique within the workflow.",
                        )
                    )
                step_ids.append(step.id)

            if not step.name:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.MISSING_STEP_NAME,
                        severity=ValidationSeverity.ERROR,
                        message=f"Step '{step.id}' is missing a name.",
                        location=f"steps.{step.id}.name",
                        related_entity=step.id,
                        suggested_fix="Define a name for this step.",
                    )
                )

            if step.timeout is not None and step.timeout <= 0:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.INVALID_TIMEOUT,
                        severity=ValidationSeverity.ERROR,
                        message=f"Step '{step.id}' has an invalid timeout of {step.timeout}.",
                        location=f"steps.{step.id}.timeout",
                        related_entity=step.id,
                        suggested_fix="Timeout value must be greater than zero.",
                    )
                )
            elif step.timeout is not None and step.timeout > 3600:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.LONG_TIMEOUT,
                        severity=ValidationSeverity.INFO,
                        message=f"Step '{step.id}' has a timeout exceeding 1 hour ({step.timeout}s).",
                        location=f"steps.{step.id}.timeout",
                        related_entity=step.id,
                        suggested_fix="Confirm that step is expected to block worker resources for so long.",
                    )
                )

            if step.retry_count < 0:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.INVALID_RETRY_COUNT,
                        severity=ValidationSeverity.ERROR,
                        message=f"Step '{step.id}' retry_count '{step.retry_count}' is negative.",
                        location=f"steps.{step.id}.retry_count",
                        related_entity=step.id,
                        suggested_fix="Retry count must be zero or a positive integer.",
                    )
                )
            elif step.retry_count > 5:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.LARGE_RETRY_COUNT,
                        severity=ValidationSeverity.INFO,
                        message=f"Step '{step.id}' has a large retry limit ({step.retry_count}).",
                        location=f"steps.{step.id}.retry_count",
                        related_entity=step.id,
                        suggested_fix="High retry counts can prolong workflow failure duration under outages.",
                    )
                )

            if not step.enabled:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.DISABLED_STEP,
                        severity=ValidationSeverity.WARNING,
                        message=f"Step '{step.id}' is disabled.",
                        location=f"steps.{step.id}.enabled",
                        related_entity=step.id,
                        suggested_fix="Remove or re-enable the step before deployment.",
                    )
                )

    @staticmethod
    def _validate_dependencies(
        workflow: WorkflowDefinition, step_ids: set[str], issues: list[ValidationIssue]
    ) -> None:
        for step in workflow.steps:
            seen_deps = set()
            for dep in step.depends_on:
                if dep == step.id:
                    issues.append(
                        ValidationIssue(
                            code=ValidationCode.SELF_DEPENDENCY,
                            severity=ValidationSeverity.ERROR,
                            message=f"Step '{step.id}' declares a dependency on itself.",
                            location=f"steps.{step.id}.depends_on",
                            related_entity=step.id,
                            suggested_fix="Remove step ID from its own depends_on list.",
                        )
                    )
                elif dep in seen_deps:
                    issues.append(
                        ValidationIssue(
                            code=ValidationCode.DUPLICATE_DEPENDENCY,
                            severity=ValidationSeverity.WARNING,
                            message=f"Step '{step.id}' lists duplicate dependency '{dep}'.",
                            location=f"steps.{step.id}.depends_on",
                            related_entity=step.id,
                            suggested_fix="Deduplicate depends_on IDs list.",
                        )
                    )
                elif dep not in step_ids:
                    issues.append(
                        ValidationIssue(
                            code=ValidationCode.MISSING_DEPENDENCY,
                            severity=ValidationSeverity.ERROR,
                            message=f"Step '{step.id}' depends on missing step ID: '{dep}'",
                            location=f"steps.{step.id}.depends_on",
                            related_entity=step.id,
                            suggested_fix=f"Add step '{dep}' or remove it from the dependency list.",
                        )
                    )
                seen_deps.add(dep)

    @staticmethod
    def _validate_dag(
        workflow: WorkflowDefinition, step_ids: set[str], issues: list[ValidationIssue]
    ) -> tuple[bool, list[str]]:
        adj: dict[str, list[str]] = {s.id: [] for s in workflow.steps}
        in_degree: dict[str, int] = {s.id: 0 for s in workflow.steps}

        for step in workflow.steps:
            for dep in step.depends_on:
                if dep in adj:
                    adj[dep].append(step.id)
                    in_degree[step.id] += 1

        queue = [node for node, deg in in_degree.items() if deg == 0]
        sorted_steps = []

        while queue:
            node = queue.pop(0)
            sorted_steps.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_steps) != len(workflow.steps):
            unprocessed = set(step_ids) - set(sorted_steps)
            issues.append(
                ValidationIssue(
                    code=ValidationCode.CIRCULAR_DEPENDENCY,
                    severity=ValidationSeverity.ERROR,
                    message="Cyclic dependency loop detected within workflow steps.",
                    location="steps",
                    related_entity=", ".join(unprocessed),
                    suggested_fix="Refactor step dependencies to form a Directed Acyclic Graph (DAG).",
                )
            )
            # Find orphan/unreachable steps if cycle exists
            for step_id in unprocessed:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.UNREACHABLE_STEP,
                        severity=ValidationSeverity.ERROR,
                        message=f"Step '{step_id}' is unreachable due to cyclic loops.",
                        location=f"steps.{step_id}",
                        related_entity=step_id,
                        suggested_fix="Break cyclic loop dependencies.",
                    )
                )
            return True, []

        return False, sorted_steps

    @staticmethod
    def _validate_mappings(
        workflow: WorkflowDefinition,
        step_ids: set[str],
        referenced_vars: set[str],
        referenced_outputs: dict[str, set[str]],
        issues: list[ValidationIssue],
    ) -> None:
        # Build ancestor map to check path reachability
        ancestor_map: dict[str, set[str]] = {}
        for s in workflow.steps:
            ancestor_map[s.id] = set()
            WorkflowValidator._gather_ancestors(s.id, workflow, ancestor_map)

        for step in workflow.steps:
            WorkflowValidator._validate_input_node(
                step.id,
                step.input,
                workflow,
                step_ids,
                ancestor_map[step.id],
                referenced_vars,
                referenced_outputs,
                issues,
            )

    @staticmethod
    def _gather_ancestors(
        step_id: str, workflow: WorkflowDefinition, ancestor_map: dict[str, set[str]]
    ) -> None:
        step = next((s for s in workflow.steps if s.id == step_id), None)
        if step is None:
            return
        for dep in step.depends_on:
            if dep not in ancestor_map[step_id]:
                # Only traverse if the dependency step actually exists in the workflow definition
                dep_exists = any(s.id == dep for s in workflow.steps)
                if dep_exists:
                    ancestor_map[step_id].add(dep)
                    # Recurse
                    WorkflowValidator._gather_ancestors(dep, workflow, ancestor_map)
                    if dep in ancestor_map:
                        ancestor_map[step_id].update(ancestor_map[dep])

    @staticmethod
    def _validate_input_node(
        step_id: str,
        node: Any,
        workflow: WorkflowDefinition,
        step_ids: set[str],
        ancestors: set[str],
        referenced_vars: set[str],
        referenced_outputs: dict[str, set[str]],
        issues: list[ValidationIssue],
    ) -> None:
        if isinstance(node, dict):
            for v in node.values():
                WorkflowValidator._validate_input_node(
                    step_id,
                    v,
                    workflow,
                    step_ids,
                    ancestors,
                    referenced_vars,
                    referenced_outputs,
                    issues,
                )
        elif isinstance(node, list):
            for item in node:
                WorkflowValidator._validate_input_node(
                    step_id,
                    item,
                    workflow,
                    step_ids,
                    ancestors,
                    referenced_vars,
                    referenced_outputs,
                    issues,
                )
        elif isinstance(node, str):
            # Check for bad prefix formats or invalid syntax
            if node.startswith("${") and not node.endswith("}"):
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.INVALID_REF_SYNTAX,
                        severity=ValidationSeverity.ERROR,
                        message=f"Step '{step_id}' contains invalid reference syntax string: '{node}'",
                        location=f"steps.{step_id}.input",
                        related_entity=step_id,
                        suggested_fix="Verify reference expression wraps closing bracket correctly, e.g. ${workflow.name}",
                    )
                )
                return

            ref = parse_reference(node)
            if ref is not None:
                if ref["type"] == "workflow":
                    var_name = ref["variable"]
                    referenced_vars.add(var_name)
                    if var_name not in workflow.variables:
                        issues.append(
                            ValidationIssue(
                                code=ValidationCode.UNKNOWN_VARIABLE_REF,
                                severity=ValidationSeverity.ERROR,
                                message=f"Step '{step_id}' references unknown workflow variable: '{var_name}'",
                                location=f"steps.{step_id}.input",
                                related_entity=step_id,
                                suggested_fix=f"Define variable '{var_name}' in the variables block.",
                            )
                        )
                elif ref["type"] == "step":
                    ref_step_id = ref["step_id"]
                    path = ref["path"]

                    # Check if referenced step exists
                    if ref_step_id not in step_ids:
                        issues.append(
                            ValidationIssue(
                                code=ValidationCode.UNKNOWN_STEP_REF,
                                severity=ValidationSeverity.ERROR,
                                message=f"Step '{step_id}' references unknown step ID: '{ref_step_id}'",
                                location=f"steps.{step_id}.input",
                                related_entity=step_id,
                                suggested_fix=f"Ensure step '{ref_step_id}' is defined in steps list.",
                            )
                        )
                    else:
                        # Check dependency ordering
                        if ref_step_id not in ancestors:
                            issues.append(
                                ValidationIssue(
                                    code=ValidationCode.MISSING_PRODUCER_DEPENDENCY,
                                    severity=ValidationSeverity.ERROR,
                                    message=f"Step '{step_id}' references output of step '{ref_step_id}' but does not declare a dependency on it.",
                                    location=f"steps.{step_id}.input",
                                    related_entity=step_id,
                                    suggested_fix=f"Add '{ref_step_id}' to step '{step_id}' depends_on list.",
                                )
                            )

                        # Record referenced step outputs
                        if ref_step_id not in referenced_outputs:
                            referenced_outputs[ref_step_id] = set()
                        if path:
                            referenced_outputs[ref_step_id].add(path[0])

    @staticmethod
    def _check_unused_entities(
        workflow: WorkflowDefinition,
        referenced_vars: set[str],
        referenced_outputs: dict[str, set[str]],
        issues: list[ValidationIssue],
    ) -> None:
        # Variables
        for var_name in workflow.variables:
            if var_name not in referenced_vars:
                issues.append(
                    ValidationIssue(
                        code=ValidationCode.UNUSED_VARIABLE,
                        severity=ValidationSeverity.WARNING,
                        message=f"Workflow variable '{var_name}' is declared but never referenced.",
                        location=f"variables.{var_name}",
                        related_entity=var_name,
                        suggested_fix="Remove variable from definition if no longer needed.",
                    )
                )

        # Outputs
        for step in workflow.steps:
            defined_outputs = set(step.output.keys())
            ref_outs = referenced_outputs.get(step.id, set())
            for out_key in defined_outputs:
                if out_key not in ref_outs:
                    issues.append(
                        ValidationIssue(
                            code=ValidationCode.UNUSED_OUTPUT,
                            severity=ValidationSeverity.WARNING,
                            message=f"Step '{step.id}' output '{out_key}' is declared but never referenced by downstream steps.",
                            location=f"steps.{step.id}.output.{out_key}",
                            related_entity=step.id,
                            suggested_fix="Verify if downstream mapping was missed, or remove unused key.",
                        )
                    )

    @staticmethod
    def _compile_statistics(
        workflow: WorkflowDefinition, has_cycle: bool
    ) -> ValidationStatistics:
        steps_count = len(workflow.steps)
        var_count = len(workflow.variables)

        # Dependencies count
        dep_count = sum(len(s.depends_on) for s in workflow.steps)

        # Root steps (no dependencies)
        root_count = sum(1 for s in workflow.steps if not s.depends_on)

        # Leaf steps (no one depends on them)
        children_ids = set()
        for s in workflow.steps:
            children_ids.update(s.depends_on)
        leaf_count = sum(1 for s in workflow.steps if s.id not in children_ids)

        # Max graph depth
        max_depth = 0
        if not has_cycle and steps_count > 0:
            # Simple longest path in DAG using dynamic programming
            depths: dict[str, int] = {}

            def get_depth(step_id: str) -> int:
                if step_id in depths:
                    return depths[step_id]
                step = next((s for s in workflow.steps if s.id == step_id), None)
                if step is None:
                    depths[step_id] = 0
                    return 0
                if not step.depends_on:
                    depths[step_id] = 1
                    return 1
                valid_deps = [
                    d for d in step.depends_on if any(s.id == d for s in workflow.steps)
                ]
                if not valid_deps:
                    depths[step_id] = 1
                    return 1
                depths[step_id] = max(get_depth(d) for d in valid_deps) + 1
                return depths[step_id]

            max_depth = max(get_depth(s.id) for s in workflow.steps)

        return ValidationStatistics(
            step_count=steps_count,
            variable_count=var_count,
            dependency_count=dep_count,
            max_graph_depth=max_depth,
            root_step_count=root_count,
            leaf_step_count=leaf_count,
        )
