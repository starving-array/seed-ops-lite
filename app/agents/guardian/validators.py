"""Validation utilities for the Guardian Planner."""

from app.agents.guardian.exceptions import GuardianPlannerException
from app.agents.schema_validation.models import SchemaValidationReport


def validate_validation_report(report: SchemaValidationReport) -> None:
    """Ensure the schema validation report does not have a failed status.

    Args:
        report: The SchemaValidationReport to check.

    Raises:
        GuardianPlannerException: If the report indicates a 'fail' status.
    """
    if report.overall_status.lower() == "fail":
        raise GuardianPlannerException(
            f"Schema validation failed (status: '{report.overall_status}'). "
            "Please fix all critical schema findings before generating an execution plan."
        )
