"""Exception classes for the Workflow Engine."""


class WorkflowException(Exception):
    """Base exception for all workflow-related errors."""

    pass


class InvalidStateTransitionError(WorkflowException):
    """Raised when an invalid state machine transition is attempted."""

    pass


class WorkflowValidationError(WorkflowException):
    """Raised when a workflow or execution plan fails validation."""

    pass


class WorkflowExecutionError(WorkflowException):
    """Raised when a workflow execution encounters a runtime failure."""

    pass
