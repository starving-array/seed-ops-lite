"""Unit and integration tests verifying Multi-Agent Scheduler & Conflict Resolution."""

import time

import pytest

from app.agents.collaboration.scheduler import (
    MultiAgentScheduler,
    SchedulingPolicy,
)
from app.platform.configuration.settings import platform_settings


@pytest.fixture
def scheduler() -> MultiAgentScheduler:
    return MultiAgentScheduler()


def test_fifo_scheduling(scheduler: MultiAgentScheduler) -> None:
    """Verify tasks execute in order of timestamp/arrival."""
    # 1. Fill concurrency slots
    limit = platform_settings.MULTI_AGENT_MAX_CONCURRENT_AGENTS
    for i in range(limit):
        res = scheduler.schedule_task(f"t-direct-{i}", f"agent-{i}")
        assert res is True

    # 2. Queue three tasks with FIFO policy
    scheduler.schedule_task(
        "t-q1", "agent-busy", priority=1, policy=SchedulingPolicy.FIFO
    )
    time.sleep(0.01)
    scheduler.schedule_task(
        "t-q2", "agent-busy", priority=5, policy=SchedulingPolicy.FIFO
    )
    time.sleep(0.01)
    scheduler.schedule_task(
        "t-q3", "agent-busy", priority=2, policy=SchedulingPolicy.FIFO
    )

    assert len(scheduler.queue) == 3
    # First item completed
    scheduler.complete_task("t-direct-0")

    # The oldest FIFO task ('t-q1') should have been dispatched next
    assert "t-q1" in scheduler.active_assignments
    assert "t-q1" not in [item["task_id"] for item in scheduler.queue]


def test_priority_scheduling(scheduler: MultiAgentScheduler) -> None:
    """Verify queue sorts items prioritizing high priority field values first."""
    # 1. Fill concurrency slots
    limit = platform_settings.MULTI_AGENT_MAX_CONCURRENT_AGENTS
    for i in range(limit):
        scheduler.schedule_task(f"t-direct-{i}", f"agent-{i}")

    # 2. Queue three tasks with different priorities
    scheduler.schedule_task(
        "t-low", "agent-busy", priority=1, policy=SchedulingPolicy.PRIORITY
    )
    scheduler.schedule_task(
        "t-high", "agent-busy", priority=10, policy=SchedulingPolicy.PRIORITY
    )
    scheduler.schedule_task(
        "t-mid", "agent-busy", priority=5, policy=SchedulingPolicy.PRIORITY
    )

    assert len(scheduler.queue) == 3

    # Free a slot
    scheduler.complete_task("t-direct-0")

    # High priority task ('t-high') should be dispatched next
    assert "t-high" in scheduler.active_assignments
    assert "t-high" not in [item["task_id"] for item in scheduler.queue]


def test_circular_dependency_rejection(scheduler: MultiAgentScheduler) -> None:
    """Verify circular dependency paths are rejected by graph planners."""
    scheduler.planner.add_task("t1", ["t2"])

    # Adding t2 depending on t1 creates a loop (t1 -> t2 -> t1)
    res = scheduler.schedule_task("t2", "agent-1", dependencies=["t1"])
    assert res is False
    assert scheduler.statistics.rejected_tasks == 1


def test_duplicate_task_prevention(scheduler: MultiAgentScheduler) -> None:
    """Verify duplicate active tasks are resolved by rejecting them."""
    # Schedule first
    res1 = scheduler.schedule_task("t-dup", "agent-1")
    assert res1 is True

    # Try duplicate while active -> Should fail/reject
    res2 = scheduler.schedule_task("t-dup", "agent-1")
    assert res2 is False
    assert scheduler.statistics.rejected_tasks == 1
