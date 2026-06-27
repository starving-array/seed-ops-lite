"""Worker implementation responsible for execution lifecycle and metrics collection."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.workers.exceptions import WorkerBusyError, WorkerStoppedError
from app.workers.models import (
    ExecutionUnit,
    WorkerHealth,
    WorkerMetrics,
    WorkerResult,
    WorkerStatus,
)
from app.workers.models import (
    Worker as WorkerModel,
)
from app.workers.telemetry import WorkerTelemetry


class Worker:
    """Infrastructure-only worker instance managing execution state and metrics."""

    def __init__(
        self,
        worker_id: str,
        executor_fn: Callable[[ExecutionUnit], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        """Initialize the Worker.

        Args:
            worker_id: Unique identifier for this worker.
            executor_fn: Async callback performing actual work task logic.
        """
        self.worker_id = worker_id
        self.status = WorkerStatus.IDLE
        self.last_heartbeat = time.time()
        self.is_healthy = True
        self.status_message = "Healthy"
        self._is_executing = False

        self.metrics = WorkerMetrics()
        self.executor_fn = executor_fn

        # Emit startup event
        WorkerTelemetry.log_worker_started(self.worker_id)

    def heartbeat(self) -> WorkerHealth:
        """Update last heartbeat timestamp and return current health status.

        Returns:
            WorkerHealth: The current worker health model.
        """
        if self.status == WorkerStatus.STOPPED:
            self.is_healthy = False
            self.status_message = "Stopped"

        self.last_heartbeat = time.time()
        WorkerTelemetry.log_worker_heartbeat(self.worker_id, self.is_healthy)

        return WorkerHealth(
            is_healthy=self.is_healthy,
            last_heartbeat=self.last_heartbeat,
            status_message=self.status_message,
        )

    async def execute(self, unit: ExecutionUnit) -> WorkerResult:
        """Execute the assigned ExecutionUnit.

        Args:
            unit: The ExecutionUnit task container to run.

        Returns:
            WorkerResult: The outcome of executing the task.

        Raises:
            WorkerStoppedError: If the worker is stopped.
            WorkerBusyError: If the worker is already executing another task.
        """
        if self.status == WorkerStatus.STOPPED:
            raise WorkerStoppedError(
                f"Worker '{self.worker_id}' is stopped and cannot execute units."
            )
        if self._is_executing:
            raise WorkerBusyError(
                f"Worker '{self.worker_id}' is busy executing another unit."
            )

        self._is_executing = True
        self.status = WorkerStatus.BUSY
        WorkerTelemetry.log_execution_started(self.worker_id, unit.unit_id)

        start_time = time.perf_counter()
        success = False
        error_msg = None
        task_metrics: dict[str, Any] = {}

        try:
            if self.executor_fn:
                # Pluggable execution callback
                task_metrics = await self.executor_fn(unit)
            else:
                # Default baseline execution simulation
                await self._simulate_execution(unit)
            success = True
        except Exception as exc:
            error_msg = str(exc)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Update metrics
            self.metrics.execution_count += 1
            if success:
                self.metrics.success_count += 1
            else:
                self.metrics.failure_count += 1
            self.metrics.total_execution_time_ms += duration_ms

            self._is_executing = False
            # Reset status if not shut down during execution
            if self.status != WorkerStatus.STOPPED:
                self.status = WorkerStatus.IDLE

            WorkerTelemetry.log_execution_completed(
                self.worker_id, unit.unit_id, duration_ms, success
            )

        return WorkerResult(
            unit_id=unit.unit_id,
            worker_id=self.worker_id,
            success=success,
            execution_time_ms=duration_ms,
            error_message=error_msg,
            metrics=task_metrics,
        )

    async def _simulate_execution(self, unit: ExecutionUnit) -> None:
        """Internal baseline simulation helper for infrastructure testing."""
        # Simple simulated sleep if requested in payload
        sim_duration = unit.payload.get("simulate_duration_seconds", 0.0)
        if sim_duration > 0:
            import asyncio

            await asyncio.sleep(sim_duration)

        # Simulate failures for testing paths
        if unit.payload.get("simulate_failure", False):
            raise RuntimeError(
                unit.payload.get("failure_message", "Simulated task failure.")
            )

    def shutdown(self) -> None:
        """Gracefully stop the worker, setting status to STOPPED."""
        self.status = WorkerStatus.STOPPED
        self.is_healthy = False
        self.status_message = "Stopped"
        WorkerTelemetry.log_worker_stopped(self.worker_id)

    def get_state_snapshot(self) -> WorkerModel:
        """Get a read-only Pydantic model representation of the worker state.

        Returns:
            WorkerModel: Snapshot of worker configuration and metrics.
        """
        health = WorkerHealth(
            is_healthy=self.is_healthy,
            last_heartbeat=self.last_heartbeat,
            status_message=self.status_message,
        )
        return WorkerModel(
            worker_id=self.worker_id,
            status=self.status,
            health=health,
            metrics=self.metrics,
        )
