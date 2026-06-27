"""MetricsAggregator consolidating and summing stage metrics."""

from typing import Any, Literal

from app.observability.collector import MetricsCollector
from app.observability.metrics import PipelineMetrics
from app.observability.models import ExecutionSummary


class MetricsAggregator:
    """Aggregates collected metrics across pipeline stages and execution summaries."""

    def __init__(self, collector: MetricsCollector) -> None:
        """Initialize MetricsAggregator with a metrics collector."""
        self.collector = collector

    def aggregate_pipeline_metrics(self) -> PipelineMetrics:
        """Combine all stage performance metrics into a single PipelineMetrics container."""
        data = self.collector.get_data()
        stages = data["stages"]

        # Calculate total stage duration if start/end times aren't fully populated
        total_duration: float | Literal["Unknown", "Not Yet Measured"] = (
            "Not Yet Measured"
        )
        if data["start_time"] is not None and data["end_time"] is not None:
            total_duration = (data["end_time"] - data["start_time"]) * 1000.0
        elif stages:
            durations = [s.metrics.duration_ms for s in stages.values()]
            total_duration = self._safe_sum(durations)

        return PipelineMetrics(
            stages=stages,
            total_duration_ms=total_duration,
            total_records=data["total_records"],
            total_tables=data["total_tables"],
            total_file_size_bytes=data["total_file_size_bytes"],
        )

    def calculate_summary(self) -> ExecutionSummary:
        """Compute status counts and execution summaries for the run."""
        data = self.collector.get_data()
        stages = data["stages"]

        success_count = sum(1 for s in stages.values() if s.status == "completed")
        failure_count = sum(1 for s in stages.values() if s.status == "failed")

        status = "completed"
        if failure_count > 0:
            status = "failed"
        elif not stages:
            status = "pending"

        duration: float | Literal["Unknown", "Not Yet Measured"] = "Not Yet Measured"
        if data["start_time"] is not None and data["end_time"] is not None:
            duration = (data["end_time"] - data["start_time"]) * 1000.0

        import datetime

        start_str = (
            datetime.datetime.fromtimestamp(
                data["start_time"], datetime.UTC
            ).isoformat()
            if data["start_time"]
            else None
        )
        end_str = (
            datetime.datetime.fromtimestamp(data["end_time"], datetime.UTC).isoformat()
            if data["end_time"]
            else None
        )

        return ExecutionSummary(
            status=status,
            start_time=start_str,
            end_time=end_str,
            duration_ms=duration,
            stages_executed=len(stages),
            success_count=success_count,
            failure_count=failure_count,
        )

    def _safe_sum(
        self, values: list[Any]
    ) -> float | Literal["Unknown", "Not Yet Measured"]:
        """Safely sum metrics filtering out string status placeholders."""
        numbers = [v for v in values if isinstance(v, int | float)]
        if not numbers:
            return "Not Yet Measured"
        return sum(numbers)
