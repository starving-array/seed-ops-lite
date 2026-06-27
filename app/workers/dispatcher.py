"""Dispatcher assigning execution units to available workers in order."""

import asyncio
from collections import defaultdict

from app.workers.exceptions import DispatcherError, WorkerNotFoundError
from app.workers.models import ExecutionUnit, WorkerResult
from app.workers.pool import WorkerPool


class Dispatcher:
    """Dispatches execution units to workers in a pool, respecting order and parallelism."""

    def __init__(self, pool: WorkerPool) -> None:
        """Initialize Dispatcher.

        Args:
            pool: WorkerPool reference to allocate workers from.
        """
        self.pool = pool

    async def dispatch(
        self, units: list[ExecutionUnit], parallel: bool = True
    ) -> list[WorkerResult]:
        """Dispatch a list of execution units respecting execution order.

        Args:
            units: List of ExecutionUnits to run.
            parallel: Whether to execute independent groups in parallel.

        Returns:
            List[WorkerResult]: Results of all executed units.

        Raises:
            DispatcherError: If execution fails or no workers are available.
        """
        if not units:
            return []

        # Group units by execution_order to respect dependency levels
        ordered_groups = defaultdict(list)
        for unit in units:
            ordered_groups[unit.execution_order].append(unit)

        results: list[WorkerResult] = []

        # Process each execution order level sequentially to respect dependencies
        for order in sorted(ordered_groups.keys()):
            group_units = ordered_groups[order]

            if parallel:
                # Concurrently execute units within the same execution order group
                tasks = [self._execute_unit_with_retry(unit) for unit in group_units]
                group_results = await asyncio.gather(*tasks, return_exceptions=True)

                for r in group_results:
                    if isinstance(r, BaseException):
                        raise DispatcherError(
                            f"Parallel dispatch execution failed: {r}"
                        ) from r
                    results.append(r)
            else:
                # Sequentially execute units within this execution order group
                for unit in group_units:
                    try:
                        res = await self._execute_unit_with_retry(unit)
                        results.append(res)
                    except Exception as exc:
                        raise DispatcherError(
                            f"Sequential dispatch execution failed: {exc}"
                        ) from exc

        return results

    async def _execute_unit_with_retry(self, unit: ExecutionUnit) -> WorkerResult:
        """Helper to allocate a worker (retrying if busy) and execute the unit.

        Args:
            unit: The ExecutionUnit to run.

        Returns:
            WorkerResult: Output of the execution.
        """
        max_attempts = 100
        attempt = 0
        worker = None

        # Wait loop for a free worker in the pool
        while attempt < max_attempts:
            try:
                worker = self.pool.allocate_any()
                break
            except WorkerNotFoundError:
                await asyncio.sleep(0.01)
                attempt += 1

        if not worker:
            raise DispatcherError(
                f"No available workers in pool to execute unit '{unit.unit_id}'."
            )

        try:
            # Run the unit on the allocated worker
            return await worker.execute(unit)
        finally:
            # Ensure the worker is released back to IDLE state
            self.pool.release(worker.worker_id)
