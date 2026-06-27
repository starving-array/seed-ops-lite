"""MetricsCollector implementation managing state and recording metrics."""

import threading
import time
import uuid
from typing import Any, ClassVar, Literal

from app.export.models import ExportResult
from app.llm.models import LLMResponse
from app.observability.exceptions import MetricsCollectionException
from app.observability.metrics import ExecutionMetrics, ResourceUsage, StageMetrics


class MetricsCollector:
    """Collects and stores measured execution metrics across the pipeline."""

    _global_data: ClassVar[dict[str, dict[str, Any]]] = {}
    _lock: ClassVar[threading.RLock] = threading.RLock()

    def __init__(self, execution_id: str | None = None) -> None:
        """Initialize MetricsCollector with an execution tracking ID."""
        self.execution_id = execution_id or str(uuid.uuid4())
        with self._lock:
            if self.execution_id not in self._global_data:
                self._global_data[self.execution_id] = {
                    "stages": {},
                    "total_records": "Not Yet Measured",
                    "total_tables": "Not Yet Measured",
                    "total_file_size_bytes": "Not Yet Measured",
                    "start_time": None,
                    "end_time": None,
                }

    def get_data(self) -> dict[str, Any]:
        """Retrieve the raw data state dictionary for the current tracking ID."""
        with self._lock:
            data = self._global_data.get(self.execution_id)
            if data is None:
                raise MetricsCollectionException(
                    f"No metrics data found for execution tracking ID '{self.execution_id}'"
                )
            return data

    def start_pipeline(self, start_time: float | None = None) -> None:
        """Record the start of pipeline execution."""
        with self._lock:
            data = self.get_data()
            data["start_time"] = start_time or time.time()

    def end_pipeline(self, end_time: float | None = None) -> None:
        """Record the termination of pipeline execution."""
        with self._lock:
            data = self.get_data()
            data["end_time"] = end_time or time.time()

    def record_stage(
        self,
        stage_name: str,
        status: str,
        duration_ms: (
            float | Literal["Unknown", "Not Yet Measured"]
        ) = "Not Yet Measured",
        resource_usage: ResourceUsage | None = None,
        errors: list[str] | None = None,
        warnings: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record performance measurements and outcome details of a step stage."""
        with self._lock:
            data = self.get_data()
            stages = data["stages"]

            if stage_name in stages:
                # Update existing stage properties
                stage: StageMetrics = stages[stage_name]
                stage.status = status
                if duration_ms != "Not Yet Measured":
                    stage.metrics.duration_ms = duration_ms
                if resource_usage:
                    stage.metrics.resource_usage = resource_usage
                if errors:
                    stage.errors.extend(errors)
                if warnings:
                    stage.warnings.extend(warnings)
                if metadata:
                    stage.metadata.update(metadata)
            else:
                # Create new stage metrics record
                stages[stage_name] = StageMetrics(
                    stage_name=stage_name,
                    status=status,
                    metrics=ExecutionMetrics(
                        duration_ms=duration_ms,
                        resource_usage=resource_usage or ResourceUsage(),
                    ),
                    errors=errors or [],
                    warnings=warnings or [],
                    metadata=metadata or {},
                )

    def record_llm_usage(
        self,
        stage_name: str,
        prompt_tokens: (
            int | Literal["Unknown", "Not Yet Measured"]
        ) = "Not Yet Measured",
        completion_tokens: (
            int | Literal["Unknown", "Not Yet Measured"]
        ) = "Not Yet Measured",
        total_tokens: int | Literal["Unknown", "Not Yet Measured"] = "Not Yet Measured",
        cost_usd: float | Literal["Unknown", "Not Yet Measured"] = "Not Yet Measured",
        calls_count: int = 1,
    ) -> None:
        """Record measured LLM usage token statistics for a stage."""
        with self._lock:
            data = self.get_data()
            stages = data["stages"]

            self.record_stage(stage_name=stage_name, status="running")
            stage: StageMetrics = stages[stage_name]

            # Invocations count accumulator
            curr_calls = stage.metrics.llm_calls
            if isinstance(curr_calls, int):
                stage.metrics.llm_calls = curr_calls + calls_count
            else:
                stage.metrics.llm_calls = calls_count

            # Helper to accumulate values safely
            def acc(curr: Any, delta: Any) -> Any:
                if isinstance(curr, int | float) and isinstance(delta, int | float):
                    return curr + delta
                if isinstance(delta, int | float):
                    return delta
                return curr

            stage.metrics.prompt_tokens = acc(
                stage.metrics.prompt_tokens, prompt_tokens
            )
            stage.metrics.completion_tokens = acc(
                stage.metrics.completion_tokens, completion_tokens
            )
            stage.metrics.total_tokens = acc(stage.metrics.total_tokens, total_tokens)
            stage.metrics.llm_cost_usd = acc(stage.metrics.llm_cost_usd, cost_usd)

    def record_gateway_response(self, stage_name: str, response: LLMResponse) -> None:
        """Extract and record usage token data directly from an LLMResponse."""
        usage = response.usage
        self.record_llm_usage(
            stage_name=stage_name,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=usage.estimated_cost,
            calls_count=1,
        )

    def record_export(
        self,
        total_records: (
            int | Literal["Unknown", "Not Yet Measured"]
        ) = "Not Yet Measured",
        total_tables: int | Literal["Unknown", "Not Yet Measured"] = "Not Yet Measured",
        file_size_bytes: (
            int | Literal["Unknown", "Not Yet Measured"]
        ) = "Not Yet Measured",
    ) -> None:
        """Record global export execution stats."""
        with self._lock:
            data = self.get_data()
            if total_records != "Not Yet Measured":
                data["total_records"] = total_records
            if total_tables != "Not Yet Measured":
                data["total_tables"] = total_tables
            if file_size_bytes != "Not Yet Measured":
                data["total_file_size_bytes"] = file_size_bytes

    def record_export_result(self, result: ExportResult) -> None:
        """Extract and record statistics directly from an ExportResult."""
        self.record_export(
            total_records=result.statistics.total_records,
            total_tables=result.statistics.total_tables,
            file_size_bytes=result.statistics.file_size_bytes,
        )

    def release(self) -> None:
        """Remove the execution data from the in-memory static store to prevent memory leaks."""
        with self._lock:
            self._global_data.pop(self.execution_id, None)

    def __enter__(self) -> "MetricsCollector":
        """Enter execution context manager block."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit execution context manager block, releasing metrics resources."""
        self.release()
