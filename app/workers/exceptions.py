"""Custom exception classes for the Worker Framework."""


class WorkerException(Exception):
    """Base exception for all worker-related errors."""

    pass


class WorkerNotFoundError(WorkerException):
    """Raised when a specified worker cannot be found in the registry or pool."""

    pass


class WorkerBusyError(WorkerException):
    """Raised when trying to assign work to a busy worker."""

    pass


class WorkerStoppedError(WorkerException):
    """Raised when trying to perform operations on a stopped or terminated worker."""

    pass


class DispatcherError(WorkerException):
    """Raised when dispatching/scheduling execution units encounters issues."""

    pass


class ExecutionUnitError(WorkerException):
    """Raised when an ExecutionUnit is invalid or fails execution validation."""

    pass
