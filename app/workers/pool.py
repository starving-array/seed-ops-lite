"""WorkerPool managing active worker registration, allocations, and capacity."""

from app.workers.exceptions import WorkerNotFoundError
from app.workers.models import WorkerStatus
from app.workers.worker import Worker


class WorkerPool:
    """Manages worker allocations, releases, capacity, and scale properties."""

    def __init__(self, capacity: int = 10) -> None:
        """Initialize WorkerPool.

        Args:
            capacity: Maximum limit of registered workers.
        """
        self.capacity = capacity
        self._workers: dict[str, Worker] = {}

    def register(self, worker: Worker) -> None:
        """Register a worker in the pool.

        Args:
            worker: The worker instance to add.

        Raises:
            ValueError: If the pool has reached capacity or worker is already registered.
        """
        if worker.worker_id in self._workers:
            raise ValueError(
                f"Worker '{worker.worker_id}' is already registered in the pool."
            )
        if len(self._workers) >= self.capacity:
            raise ValueError(
                f"Cannot register worker. Pool has reached capacity of {self.capacity}."
            )
        self._workers[worker.worker_id] = worker

    def unregister(self, worker_id: str) -> None:
        """Unregister and remove a worker from the pool.

        Args:
            worker_id: The ID of the worker to remove.

        Raises:
            WorkerNotFoundError: If the worker is not in the pool.
        """
        if worker_id not in self._workers:
            raise WorkerNotFoundError(
                f"Worker '{worker_id}' not registered in the pool."
            )
        del self._workers[worker_id]

    def allocate_any(self) -> Worker:
        """Allocate any available IDLE worker.

        Returns:
            Worker: The allocated worker instance.

        Raises:
            WorkerNotFoundError: If no idle workers are available.
        """
        for worker in self._workers.values():
            if worker.status == WorkerStatus.IDLE:
                worker.status = WorkerStatus.BUSY
                return worker
        raise WorkerNotFoundError("No idle workers available in the pool.")

    def allocate(self, worker_id: str) -> Worker:
        """Allocate a specific worker by ID.

        Args:
            worker_id: Unique worker identifier.

        Returns:
            Worker: The allocated worker instance.

        Raises:
            WorkerNotFoundError: If the worker is not registered or not IDLE.
        """
        if worker_id not in self._workers:
            raise WorkerNotFoundError(
                f"Worker '{worker_id}' not registered in the pool."
            )
        worker = self._workers[worker_id]
        if worker.status != WorkerStatus.IDLE:
            raise WorkerNotFoundError(
                f"Worker '{worker_id}' is currently not IDLE (Status: {worker.status.value})."
            )
        worker.status = WorkerStatus.BUSY
        return worker

    def release(self, worker_id: str) -> None:
        """Release a worker from BUSY state back to IDLE.

        Args:
            worker_id: Unique worker identifier.

        Raises:
            WorkerNotFoundError: If the worker is not registered.
        """
        if worker_id not in self._workers:
            raise WorkerNotFoundError(
                f"Worker '{worker_id}' not registered in the pool."
            )
        worker = self._workers[worker_id]
        if worker.status == WorkerStatus.BUSY:
            worker.status = WorkerStatus.IDLE

    def resize(self, new_capacity: int) -> None:
        """Resize pool capacity to support dynamic future scaling.

        Args:
            new_capacity: The new capacity ceiling limit.

        Raises:
            ValueError: If the new capacity is less than current active worker count.
        """
        if new_capacity < len(self._workers):
            raise ValueError(
                f"Cannot reduce capacity to {new_capacity} as {len(self._workers)} workers are currently active."
            )
        self.capacity = new_capacity

    @property
    def total_capacity(self) -> int:
        """Expose total pool capacity limit."""
        return self.capacity

    @property
    def free_capacity(self) -> int:
        """Calculate and return remaining pool slot count."""
        return self.capacity - len(self._workers)

    @property
    def registered_count(self) -> int:
        """Total count of registered workers in the pool."""
        return len(self._workers)

    @property
    def idle_count(self) -> int:
        """Count of currently idle workers."""
        return sum(1 for w in self._workers.values() if w.status == WorkerStatus.IDLE)

    @property
    def busy_count(self) -> int:
        """Count of currently busy workers."""
        return sum(1 for w in self._workers.values() if w.status == WorkerStatus.BUSY)

    def get_worker(self, worker_id: str) -> Worker:
        """Retrieve a registered worker instance without changing status.

        Args:
            worker_id: Unique worker identifier.

        Returns:
            Worker: The registered worker instance.

        Raises:
            WorkerNotFoundError: If the worker is not registered.
        """
        if worker_id not in self._workers:
            raise WorkerNotFoundError(
                f"Worker '{worker_id}' not registered in the pool."
            )
        return self._workers[worker_id]

    def list_workers(self) -> list[Worker]:
        """List all worker instances managed by the pool.

        Returns:
            List[Worker]: Managed worker instances.
        """
        return list(self._workers.values())
