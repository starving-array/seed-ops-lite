"""Executive models representing pipeline reports and summaries."""

from typing import Literal

from pydantic import BaseModel, Field

from app.observability.metrics import PipelineMetrics, ResourceUsage  # noqa: F401


class ExecutionSummary(BaseModel):
    """High-level executive summary of a pipeline execution run."""

    status: str = Field(
        ...,
        description="Overall pipeline status outcome (e.g. pending, completed, failed).",
    )
    start_time: str | None = Field(
        default=None,
        description="ISO timestamp of pipeline execution start.",
    )
    end_time: str | None = Field(
        default=None,
        description="ISO timestamp of pipeline execution termination.",
    )
    duration_ms: float | Literal["Unknown", "Not Yet Measured"] = Field(
        default="Not Yet Measured",
        description="Overall execution duration in milliseconds.",
    )
    stages_executed: int = Field(
        default=0,
        description="Count of executed stages.",
    )
    success_count: int = Field(
        default=0,
        description="Count of successfully executed stages.",
    )
    failure_count: int = Field(
        default=0,
        description="Count of failed stages.",
    )


class ExecutionReport(BaseModel):
    """Unified report consolidating metadata, metrics, and summaries of a pipeline run."""

    execution_id: str = Field(
        ...,
        description="UUID tracking code for the execution plan run.",
    )
    summary: ExecutionSummary = Field(
        ...,
        description="High-level status summary metrics.",
    )
    pipeline_metrics: PipelineMetrics = Field(
        ...,
        description="Breakdown of stage metrics and total performance metrics.",
    )
