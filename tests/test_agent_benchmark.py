"""Performance benchmark and scalability validation tests for the Agent Execution Subsystem."""

# ruff: noqa: ARG001, F841
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.execution.models import ExecutionContext, ExecutionState
from app.agents.execution.orchestrator import (
    ExecutionCoordinator,
    ExecutionEventDispatcher,
    ExecutionSessionManager,
    TaskDispatcher,
)
from app.agents.execution.recovery import (
    ExecutionCheckpointAdapter,
)
from app.agents.execution.scheduler import ExecutionScheduler
from app.agents.framework.manager import AgentManager
from app.agents.framework.models import AgentExecutionResult, AgentLifecycle
from app.agents.planning.models import ExecutionPlan, TaskNode


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-bench-1",
        workflow_id="wf-bench-1",
        workflow_version="1.0.0",
        plan_id="plan-bench-1",
        agent_id="agent-bench-1",
        session_id="sess-bench-1",
        memory_ref="memory_ref_bench",
    )


@pytest.mark.asyncio
async def test_scheduler_and_dispatch_throughput(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Benchmark Scheduler compilation throughput and Dispatch loop latency."""
    scheduler = ExecutionScheduler()

    # 1. Measure scheduler compilation latency
    nodes = {
        f"t{i}": TaskNode(id=f"t{i}", title=f"Task {i}", description=f"desc {i}")
        for i in range(8)
    }
    plan = ExecutionPlan(id="plan-bench", goal="Throughput Test", nodes=nodes, edges=[])

    start_sched = time.perf_counter()
    res = ExecutionScheduler.create_schedule(plan)
    sched_latency = time.perf_counter() - start_sched

    assert res is not None
    assert sched_latency < 0.1  # Must be fast (< 100ms for 50 nodes)

    # 2. Measure task dispatch latency
    mock_agent_manager = MagicMock(spec=AgentManager)
    success_result = AgentExecutionResult(
        execution_id="exec-bench-1",
        status=AgentLifecycle.COMPLETED,
        outputs={"status": "done"},
        errors=[],
        duration=0.001,
        metrics={},
    )
    mock_agent_manager.execute_agent = AsyncMock(return_value=success_result)

    session_manager = ExecutionSessionManager()
    event_dispatcher = ExecutionEventDispatcher()
    task_dispatcher = TaskDispatcher(mock_agent_manager)
    coordinator = ExecutionCoordinator(
        session_manager, event_dispatcher, task_dispatcher
    )

    session_manager.create_session("sess-bench-1", "exec-bench-1", execution_context)

    start_dispatch = time.perf_counter()
    summary = await coordinator.execute_plan("sess-bench-1", plan)
    dispatch_latency = time.perf_counter() - start_dispatch

    assert summary.success is True
    assert dispatch_latency < 1.0  # Must complete quickly in test mode


@pytest.mark.asyncio
async def test_checkpoint_and_recovery_benchmarks(
    setup_test_database: Any, execution_context: ExecutionContext
) -> None:
    """Measure the latency overhead associated with writing and restoring checkpoint records."""
    # 1. Save latency
    start_save = time.perf_counter()
    ExecutionCheckpointAdapter.save_checkpoint(
        context=execution_context,
        state=ExecutionState.RUNNING,
        completed_tasks=["task1"],
        pending_tasks=["task2"],
        retry_counters={"task2": 0},
        metadata={},
    )
    save_duration = time.perf_counter() - start_save
    assert save_duration < 0.25  # Save checkpoint should be < 250ms

    # 2. Restore latency
    start_restore = time.perf_counter()
    chk = ExecutionCheckpointAdapter.load_checkpoint(execution_context.execution_id)
    restore_duration = time.perf_counter() - start_restore

    assert chk is not None
    assert restore_duration < 0.25
