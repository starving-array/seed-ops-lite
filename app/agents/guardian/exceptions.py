"""Exception definitions for the Guardian Planner agent."""


class GuardianPlannerException(Exception):
    """Base exception for all Guardian Planner errors."""

    pass


class DependencyCycleError(GuardianPlannerException):
    """Raised when a cyclic dependency loop is detected in the database schema."""

    pass


class UnresolvedDependencyError(GuardianPlannerException):
    """Raised when a foreign key references a table not defined in the schema."""

    pass
