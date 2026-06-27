"""WorkerManager handling the creation, health, and clean shutdown of workers."""

import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from app.workers.exceptions import WorkerNotFoundError
from app.workers.models import ExecutionUnit, WorkerHealth
from app.workers.pool import WorkerPool
from app.workers.worker import Worker


class WorkerManager:
    """Manages worker lifecycles, creates new workers, and monitors health states."""

    def __init__(self, pool: WorkerPool | None = None) -> None:
        """Initialize WorkerManager.

        Args:
            pool: WorkerPool reference to register managed workers to.
        """
        self.pool = pool or WorkerPool()

    def create_worker(
        self,
        worker_id: str,
        executor_fn: Callable[[ExecutionUnit], Awaitable[dict[str, Any]]] | None = None,
    ) -> Worker:
        """Create, register, and return a new worker.

        Args:
            worker_id: Unique worker identifier.
            executor_fn: Pluggable execution callback.

        Returns:
            Worker: The newly created worker.
        """
        worker = Worker(worker_id=worker_id, executor_fn=executor_fn)
        self.pool.register(worker)
        return worker

    def stop_worker(self, worker_id: str) -> None:
        """Cleanly shut down and stop a specific worker.

        Args:
            worker_id: Unique worker identifier.
        """
        worker = self.pool.get_worker(worker_id)
        worker.shutdown()

    def stop_all(self) -> None:
        """Cleanly stop all registered workers in the managed pool."""
        for worker in self.pool.list_workers():
            worker.shutdown()

    def monitor_health(self) -> dict[str, WorkerHealth]:
        """Aggregate heartbeat health statuses of all registered workers.

        Returns:
            Dict[str, WorkerHealth]: Map of worker IDs to their health snapshot models.
        """
        health_report = {}
        for worker in self.pool.list_workers():
            health_report[worker.worker_id] = worker.heartbeat()
        return health_report

    def remove_worker(self, worker_id: str) -> None:
        """Stop and remove a worker from management and pool.

        Args:
            worker_id: Unique worker identifier.
        """
        with contextlib.suppress(WorkerNotFoundError):
            self.stop_worker(worker_id)
        self.pool.unregister(worker_id)
