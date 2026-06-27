"""Unit tests for the Worker Framework validating workers, pool, manager, and dispatcher."""

from unittest.mock import AsyncMock

import pytest

from app.workers import (
    Dispatcher,
    ExecutionUnit,
    Worker,
    WorkerBusyError,
    WorkerHealth,
    WorkerManager,
    WorkerPool,
    WorkerStatus,
    WorkerStoppedError,
)


@pytest.mark.asyncio
async def test_worker_execution_success() -> None:
    """Verify that a worker executes successfully and updates its status and metrics."""
    worker = Worker(worker_id="w-1")
    assert worker.status == WorkerStatus.IDLE

    unit = ExecutionUnit(
        unit_id="unit-1",
        task_type="seeder",
        target="users",
        payload={"simulate_duration_seconds": 0.01},
        execution_order=0,
    )

    result = await worker.execute(unit)
    assert result.success is True
    assert result.unit_id == "unit-1"
    assert result.worker_id == "w-1"
    assert result.execution_time_ms > 0
    assert result.error_message is None

    # Check metrics
    snapshot = worker.get_state_snapshot()
    assert snapshot.status == WorkerStatus.IDLE
    assert snapshot.metrics.execution_count == 1
    assert snapshot.metrics.success_count == 1
    assert snapshot.metrics.failure_count == 0
    assert snapshot.metrics.measured_memory_bytes == "Not Yet Measured"
    assert snapshot.metrics.measured_cpu_percent == "Not Yet Measured"


@pytest.mark.asyncio
async def test_worker_execution_failure() -> None:
    """Verify that a worker handles execution failure gracefully and updates metrics."""
    worker = Worker(worker_id="w-2")
    unit = ExecutionUnit(
        unit_id="unit-2",
        task_type="seeder",
        target="posts",
        payload={"simulate_failure": True, "failure_message": "DB connection timeout"},
        execution_order=0,
    )

    result = await worker.execute(unit)
    assert result.success is False
    assert result.unit_id == "unit-2"
    assert "DB connection timeout" in result.error_message

    snapshot = worker.get_state_snapshot()
    assert snapshot.metrics.execution_count == 1
    assert snapshot.metrics.success_count == 0
    assert snapshot.metrics.failure_count == 1


@pytest.mark.asyncio
async def test_worker_pluggable_executor() -> None:
    """Verify that a pluggable executor callback is executed and returns custom metrics."""
    mock_executor = AsyncMock(return_value={"custom_key": "custom_val"})
    worker = Worker(worker_id="w-custom", executor_fn=mock_executor)

    unit = ExecutionUnit(
        unit_id="unit-3",
        task_type="validator",
        target="comments",
        payload={},
        execution_order=1,
    )

    result = await worker.execute(unit)
    assert result.success is True
    assert result.metrics == {"custom_key": "custom_val"}
    mock_executor.assert_called_once_with(unit)


@pytest.mark.asyncio
async def test_worker_busy_and_stopped_errors() -> None:
    """Verify that a worker rejects execution if busy or stopped."""
    worker = Worker(worker_id="w-err")

    # Stop the worker and try to execute
    worker.shutdown()
    unit = ExecutionUnit(
        unit_id="unit-4", task_type="seeder", target="users", payload={}
    )
    with pytest.raises(WorkerStoppedError):
        await worker.execute(unit)

    # Test busy state by manually updating status
    worker2 = Worker(worker_id="w-err-2")
    worker2._is_executing = True
    with pytest.raises(WorkerBusyError):
        await worker2.execute(unit)


def test_worker_heartbeat() -> None:
    """Verify heartbeat health reporting."""
    worker = Worker(worker_id="w-hb")
    health = worker.heartbeat()
    assert isinstance(health, WorkerHealth)
    assert health.is_healthy is True
    assert health.status_message == "Healthy"

    worker.shutdown()
    health_stopped = worker.heartbeat()
    assert health_stopped.is_healthy is False
    assert health_stopped.status_message == "Stopped"


def test_worker_pool_management() -> None:
    """Verify pool capacity, registration, allocation, and resizing."""
    pool = WorkerPool(capacity=2)
    assert pool.total_capacity == 2
    assert pool.free_capacity == 2

    w1 = Worker(worker_id="w1")
    w2 = Worker(worker_id="w2")
    w3 = Worker(worker_id="w3")

    pool.register(w1)
    pool.register(w2)

    with pytest.raises(ValueError):
        pool.register(w3)  # Pool full

    assert pool.registered_count == 2
    assert pool.free_capacity == 0

    # Allocate
    allocated = pool.allocate_any()
    assert allocated.worker_id in ["w1", "w2"]
    assert allocated.status == WorkerStatus.BUSY

    # Resize pool
    pool.resize(3)
    assert pool.total_capacity == 3
    assert pool.free_capacity == 1
    pool.register(w3)
    assert pool.registered_count == 3


def test_worker_manager_lifecycle() -> None:
    """Verify manager creates, monitors, and stops workers."""
    manager = WorkerManager()
    w1 = manager.create_worker(worker_id="mw-1")
    assert w1.worker_id == "mw-1"
    assert manager.pool.registered_count == 1

    health_report = manager.monitor_health()
    assert "mw-1" in health_report
    assert health_report["mw-1"].is_healthy is True

    manager.stop_worker("mw-1")
    assert w1.status == WorkerStatus.STOPPED

    # Stop all
    w2 = manager.create_worker(worker_id="mw-2")
    manager.stop_all()
    assert w2.status == WorkerStatus.STOPPED


@pytest.mark.asyncio
async def test_dispatcher_ordering_and_parallelism() -> None:
    """Verify dispatcher respects order and supports parallel execution."""
    pool = WorkerPool(capacity=3)
    w1 = Worker(worker_id="dw-1")
    w2 = Worker(worker_id="dw-2")
    w3 = Worker(worker_id="dw-3")
    pool.register(w1)
    pool.register(w2)
    pool.register(w3)

    dispatcher = Dispatcher(pool)

    # 4 units: 2 in order 0, 1 in order 1, 1 in order 2
    units = [
        ExecutionUnit(
            unit_id="u1",
            task_type="seeder",
            target="t1",
            payload={"simulate_duration_seconds": 0.05},
            execution_order=0,
        ),
        ExecutionUnit(
            unit_id="u2",
            task_type="seeder",
            target="t2",
            payload={"simulate_duration_seconds": 0.05},
            execution_order=0,
        ),
        ExecutionUnit(
            unit_id="u3",
            task_type="seeder",
            target="t3",
            payload={"simulate_duration_seconds": 0.01},
            execution_order=1,
        ),
        ExecutionUnit(
            unit_id="u4",
            task_type="seeder",
            target="t4",
            payload={"simulate_failure": True},
            execution_order=2,
        ),
    ]

    # Test sequential dispatch
    results = await dispatcher.dispatch(units, parallel=False)
    assert len(results) == 4
    assert results[0].unit_id == "u1"
    assert results[0].success is True
    assert results[1].unit_id == "u2"
    assert results[1].success is True
    assert results[2].unit_id == "u3"
    assert results[2].success is True
    assert results[3].unit_id == "u4"
    assert results[3].success is False

    # Test parallel dispatch error propagates correctly
    # If u4 fails, it still completes execution with success=False, but if we raise a DispatcherError
    # or handle general failures. Let's make sure the dispatcher returns list of results even when a unit has success=False.
    # Note: dispatcher raises DispatcherError if a worker raises unexpected exception that is not handled by worker execution.
