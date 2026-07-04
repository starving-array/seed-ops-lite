"""Multi-Agent Scheduler & Conflict Resolution layer."""

# ruff: noqa: RET508, RET505, S110, PLR0911, SIM102, ARG002

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.telemetry.events import EventID


class SchedulingPolicy(str, Enum):
    """Supported multi-agent task execution scheduling policies."""

    FIFO = "FIFO"
    PRIORITY = "PRIORITY"
    ROUND_ROBIN = "ROUND_ROBIN"
    LEAST_LOADED = "LEAST_LOADED"
    FAIR_SHARE = "FAIR_SHARE"


class SchedulingStatistics(BaseModel):
    """Aggregates metrics for the multi-agent scheduler."""

    tasks_scheduled: int = 0
    scheduling_latency: float = 0.0
    scheduling_throughput: float = 0.0
    conflict_count: int = 0
    resolved_conflicts: int = 0
    rejected_tasks: int = 0
    queue_utilization: float = 0.0
    agent_utilization: float = 0.0


class ConflictResolver:
    """Detects and resolves execution conflicts including loops and resource blocks."""

    def __init__(self, scheduler: Any) -> None:
        self.scheduler = scheduler

    def detect_circular_dependencies(
        self,
        task_id: str,
        dependencies: list[str],
        dependency_graph: dict[str, list[str]],
    ) -> bool:
        """Verify if adding dependencies introduces a cycle (circular dependency)."""
        visited = set()
        rec_stack = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in temp_graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        # Build temp graph
        temp_graph = {k: list(v) for k, v in dependency_graph.items()}
        temp_graph[task_id] = dependencies

        for node in temp_graph:
            if node not in visited:
                if dfs(node):
                    return True
        return False

    def resolve_conflicts(
        self,
        task_id: str,
        assigned_agent: str,
        active_assignments: dict[str, str],
        active_locks: dict[str, Any],
    ) -> str | None:
        """Detect and attempt to resolve resource contention or duplicates.

        Returns:
          - "REJECT" if duplicate task exists.
          - "QUEUE" if agent is busy or write contention occurs.
          - None if conflict-free.
        """
        # 1. Duplicate check
        if task_id in active_assignments:
            logger.error(
                EventID.LOG_ERROR,
                f"Duplicate task '{task_id}' detected.",
                component="ConflictResolver",
            )
            return "REJECT"

        # 2. Resource/Agent contention check
        busy_agents = list(active_assignments.values())
        if assigned_agent in busy_agents:
            logger.info(
                EventID.LOG_INFO,
                f"Agent contention for '{assigned_agent}'. Queueing task '{task_id}'.",
                component="ConflictResolver",
            )
            return "QUEUE"

        return None


class ResourceAllocator:
    """Manages active slot allocations and agent concurrency limits."""

    def __init__(self) -> None:
        self.active_slots = 0

    def allocate_slot(self) -> bool:
        """Reserve a single execution slot check limits."""
        limit = platform_settings.MULTI_AGENT_MAX_CONCURRENT_AGENTS
        if self.active_slots >= limit:
            return False
        self.active_slots += 1
        return True

    def release_slot(self) -> None:
        """Free an active slot allocation."""
        if self.active_slots > 0:
            self.active_slots -= 1


class CoordinationPlanner:
    """Handles dependency checking and ordered execution path mapping."""

    def __init__(self) -> None:
        self.dependency_graph: dict[str, list[str]] = {}
        self.completed_tasks: set[str] = set()

    def add_task(self, task_id: str, dependencies: list[str]) -> None:
        """Add task to graph."""
        self.dependency_graph[task_id] = dependencies

    def is_runnable(self, task_id: str) -> bool:
        """Check if all dependencies are satisfied."""
        deps = self.dependency_graph.get(task_id, [])
        return all(d in self.completed_tasks for d in deps)

    def mark_completed(self, task_id: str) -> None:
        """Mark task completed."""
        self.completed_tasks.add(task_id)


class MultiAgentScheduler:
    """Deterministic scheduler for multi-agent execution with policy-based routing."""

    def __init__(self) -> None:
        self.resolver = ConflictResolver(self)
        self.allocator = ResourceAllocator()
        self.planner = CoordinationPlanner()
        self.statistics = SchedulingStatistics()
        self.active_assignments: dict[str, str] = {}
        self.queue: list[dict[str, Any]] = []

    def schedule_task(
        self,
        task_id: str,
        assigned_agent: str,
        priority: int = 0,
        dependencies: list[str] | None = None,
        policy: SchedulingPolicy = SchedulingPolicy.FIFO,
    ) -> bool:
        """Schedule delegated tasks checking dependency conflicts and allocations."""
        start_time = time.perf_counter()
        self.statistics.tasks_scheduled += 1

        deps = dependencies or []

        # 1. Circular dependency check
        if self.resolver.detect_circular_dependencies(
            task_id, deps, self.planner.dependency_graph
        ):
            self.statistics.conflict_count += 1
            self.statistics.rejected_tasks += 1
            logger.error(
                EventID.LOG_ERROR,
                f"Scheduling failed: Circular dependency detected for task '{task_id}'",
                component="MultiAgentScheduler",
            )
            return False

        # 2. Conflict detection
        resolution = self.resolver.resolve_conflicts(
            task_id, assigned_agent, self.active_assignments, {}
        )

        if resolution == "REJECT":
            self.statistics.conflict_count += 1
            self.statistics.rejected_tasks += 1
            return False

        if resolution == "QUEUE":
            self.statistics.conflict_count += 1
            self.statistics.resolved_conflicts += 1
            # Add to queue
            limit = platform_settings.MULTI_AGENT_MAX_SCHEDULING_QUEUE_SIZE
            if len(self.queue) >= limit:
                self.statistics.rejected_tasks += 1
                return False
            self.queue.append(
                {
                    "task_id": task_id,
                    "agent_id": assigned_agent,
                    "priority": priority,
                    "policy": policy,
                    "timestamp": time.time(),
                }
            )
            self.planner.add_task(task_id, deps)
            self.statistics.queue_utilization = len(self.queue) / limit
            logger.info(
                EventID.LOG_INFO,
                f"Task '{task_id}' queued successfully.",
                component="MultiAgentScheduler",
            )
            return True

        # 3. Resource slot allocation check
        if not self.allocator.allocate_slot():
            # Concurrency limit reached, queue task
            self.queue.append(
                {
                    "task_id": task_id,
                    "agent_id": assigned_agent,
                    "priority": priority,
                    "policy": policy,
                    "timestamp": time.time(),
                }
            )
            self.planner.add_task(task_id, deps)
            return True

        # 4. Immediate execution allocation
        self.active_assignments[task_id] = assigned_agent
        self.planner.add_task(task_id, deps)

        # Update utilization metrics
        limit_concurrency = platform_settings.MULTI_AGENT_MAX_CONCURRENT_AGENTS
        self.statistics.agent_utilization = (
            self.allocator.active_slots / limit_concurrency
        )

        duration = time.perf_counter() - start_time
        self.statistics.scheduling_latency = (
            (self.statistics.scheduling_latency + duration) / 2
            if self.statistics.scheduling_latency > 0
            else duration
        )

        logger.info(
            EventID.LOG_INFO,
            f"Task '{task_id}' scheduled directly on agent '{assigned_agent}'",
            component="MultiAgentScheduler",
        )
        return True

    def complete_task(self, task_id: str) -> None:
        """Free allocation slots and update queue schedules."""
        if task_id in self.active_assignments:
            del self.active_assignments[task_id]
            self.allocator.release_slot()
            self.planner.mark_completed(task_id)

            # Re-evaluate queued items based on policy sorting
            self._process_queue()

    def _process_queue(self) -> None:
        """Sort and process queued items."""
        if not self.queue:
            return

        # Sort queue based on target policy from first queue element
        policy = self.queue[0]["policy"]

        if policy == SchedulingPolicy.PRIORITY:
            # High priority first (reverse order)
            self.queue.sort(key=lambda x: x["priority"], reverse=True)
        elif policy == SchedulingPolicy.FIFO:
            # Oldest first
            self.queue.sort(key=lambda x: x["timestamp"])

        runnable_index = -1
        for i, item in enumerate(self.queue):
            if self.planner.is_runnable(item["task_id"]):
                # Ensure target agent is free
                if item["agent_id"] not in self.active_assignments.values():
                    runnable_index = i
                    break

        if runnable_index != -1:
            item = self.queue.pop(runnable_index)
            # Re-allocate
            if self.allocator.allocate_slot():
                self.active_assignments[item["task_id"]] = item["agent_id"]
                logger.info(
                    EventID.LOG_INFO,
                    f"Queued task '{item['task_id']}' dispatched to agent '{item['agent_id']}'",
                    component="MultiAgentScheduler",
                )
