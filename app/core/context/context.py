"""Execution context module managing async-safe request-scoped metadata."""

from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    """Execution context containing request and operational metadata."""

    request_id: str | None = Field(
        default=None, description="Unique identifier for the immediate request"
    )
    correlation_id: str | None = Field(
        default=None, description="Identifier propagating across service bounds"
    )
    trace_id: str | None = Field(default=None, description="Telemetry trace identifier")
    job_id: str | None = Field(
        default=None, description="Asynchronous background job identifier"
    )
    worker_id: str | None = Field(
        default=None, description="Worker process node identifier"
    )
    task_id: str | None = Field(
        default=None, description="Sub-task execution identifier"
    )
    workflow_id: str | None = Field(
        default=None, description="Active workflow / generation run identifier"
    )
    phase_name: str | None = Field(
        default=None, description="Workflow processing phase name"
    )
    user_id: str | None = Field(
        default=None, description="Authenticated user account identifier"
    )
    request_start_time: float | None = Field(
        default=None, description="Timestamp recording when request processing started"
    )


# Single ContextVar holding the current ExecutionContext state
_context_var: ContextVar[ExecutionContext] = ContextVar(
    "execution_context", default=ExecutionContext()
)


def get_context() -> ExecutionContext:
    """Retrieve the current execution context.

    Returns:
        ExecutionContext: The current context object.
    """
    return _context_var.get()


def set_context(context: ExecutionContext) -> Any:
    """Set the current execution context.

    Args:
        context: The execution context to set.

    Returns:
        Any: The token that can be used to reset the context.
    """
    return _context_var.set(context)


def reset_context(token: Any) -> None:
    """Reset the execution context to its previous state.

    Args:
        token: The token returned by set_context.
    """
    _context_var.reset(token)


def update_context(**kwargs: Any) -> None:
    """Update fields in the current execution context.

    Args:
        **kwargs: Key-value pairs to update in the context.
    """
    current = _context_var.get()
    updated = current.model_copy(update=kwargs)
    _context_var.set(updated)
