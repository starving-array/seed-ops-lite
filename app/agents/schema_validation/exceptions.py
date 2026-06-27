"""Exception types for the Schema Validation Agent."""


class SchemaValidationAgentException(Exception):
    """Base exception for all schema validation agent errors."""

    pass


class PlannerException(SchemaValidationAgentException):
    """Raised when there is an issue planning the skill executions."""

    pass


class AggregationException(SchemaValidationAgentException):
    """Raised when there is an issue aggregating skill findings."""

    pass
