"""Strongly typed models for the Worker Framework."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExecutionUnit(BaseModel):
    """A single unit of execution dispatched to a worker."""

    unit_id: str = Field(..., description="Unique identifier for the execution unit.")
    task_type: str = Field(
        ..., description="The type of task, e.g., seeder, validator, etc."
    )
    target: str = Field(
        ..., description="The target entity of the execution, e.g., table name."
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Task specific payload data."
    )
    execution_order: int = Field(
        default=0, description="Order index to respect execution sequence."
    )


class WorkerStatus(str, Enum):
    """Operational states of a worker."""

    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"


class WorkerHealth(BaseModel):
    """Health status and heartbeat tracking for workers."""

    is_healthy: bool = Field(..., description="Whether the worker is healthy.")
    last_heartbeat: float = Field(..., description="Timestamp of the last heartbeat.")
    status_message: str = Field(default="Healthy", description="Status message.")


class WorkerMetrics(BaseModel):
    """Execution metrics measured during worker lifetime."""

    execution_count: int = Field(default=0, description="Total executed units.")
    success_count: int = Field(default=0, description="Successful executions.")
    failure_count: int = Field(default=0, description="Failed executions.")
    total_execution_time_ms: float = Field(
        default=0.0, description="Total execution time in milliseconds."
    )

    # Measured resources (strictly measured, otherwise Unknown/Not Yet Measured)
    measured_memory_bytes: int | Literal["Unknown", "Not Yet Measured"] = Field(
        default="Not Yet Measured",
        description="Measured memory usage or placeholder if unmeasured.",
    )
    measured_cpu_percent: float | Literal["Unknown", "Not Yet Measured"] = Field(
        default="Not Yet Measured",
        description="Measured CPU usage or placeholder if unmeasured.",
    )


class Worker(BaseModel):
    """Model representing a worker's static info and runtime state snapshot."""

    worker_id: str = Field(..., description="Unique worker identifier.")
    status: WorkerStatus = Field(
        default=WorkerStatus.IDLE, description="Current worker state."
    )
    health: WorkerHealth = Field(..., description="Worker health tracking.")
    metrics: WorkerMetrics = Field(
        default_factory=WorkerMetrics, description="Collected execution metrics."
    )


class WorkerResult(BaseModel):
    """The outcome result of executing an ExecutionUnit."""

    unit_id: str = Field(..., description="ID of the execution unit.")
    worker_id: str = Field(..., description="ID of the worker that executed the unit.")
    success: bool = Field(..., description="Whether execution was successful.")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds.")
    error_message: str | None = Field(
        default=None, description="Error message if execution failed."
    )
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Measured metrics collected during execution.",
    )
