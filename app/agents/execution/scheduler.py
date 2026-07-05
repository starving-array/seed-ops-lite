"""Agent Execution Scheduler, Dependency Resolver, and Stage Builder."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.agents.planning.models import ExecutionPlan
from app.platform.configuration.settings import platform_settings


class ScheduleStatistics(BaseModel):
    """Telemetry metrics detailing scheduled stages, depths, and parallelism indices."""

    model_config = ConfigDict(frozen=True)

    total_tasks: int = 0
    stage_count: int = 0
    max_parallel_tasks: int = 0
    critical_path_length: int = 0
    dependency_count: int = 0
    execution_depth: int = 0


class ScheduleResult(BaseModel):
    """Immutable scheduled output mapping execution stages and statistics."""

    model_config = ConfigDict(frozen=True)

    schedule_id: str
    plan_id: str
    stages: list[list[str]] = Field(
        default_factory=list, description="Ordered stages containing task IDs."
    )
    statistics: ScheduleStatistics = Field(default_factory=ScheduleStatistics)


class SchedulerValidationError(Exception):
    """Exception raised on schedule validation errors."""

    pass


class ReadyQueue:
    """Dynamic task ready queue tracking unblocked, executing, and completed tasks."""

    def __init__(
        self, stages: list[list[str]], dependency_map: dict[str, set[str]]
    ) -> None:
        self._stages = stages
        self._dependencies = {k: set(v) for k, v in dependency_map.items()}
        self._completed: set[str] = set()
        self._running: set[str] = set()
        self._scheduled: set[str] = set()
        self._all_tasks: set[str] = {task for stage in stages for task in stage}

    def get_ready_tasks(self) -> list[str]:
        """Retrieve all currently unblocked tasks whose dependencies are fully satisfied.

        Returns:
            List[str]: List of unblocked task IDs.
        """
        ready = []
        for task_id in self._all_tasks:
            if (
                task_id in self._completed
                or task_id in self._running
                or task_id in self._scheduled
            ):
                continue
            # Task is ready if all its upstream dependencies are in completed set
            deps = self._dependencies.get(task_id, set())
            if deps.issubset(self._completed):
                ready.append(task_id)
        return ready

    def push_ready(self, task_id: str) -> None:
        """Mark a task as actively scheduled to prevent duplicate execution.

        Args:
            task_id: Target task node.
        """
        if task_id in self._all_tasks:
            self._scheduled.add(task_id)

    def start_task(self, task_id: str) -> None:
        """Move task from scheduled to running state."""
        if task_id in self._scheduled:
            self._scheduled.remove(task_id)
        self._running.add(task_id)

    def remove_completed(self, task_id: str) -> None:
        """Mark task as completed, releasing downstreams from dependency block."""
        if task_id in self._running:
            self._running.remove(task_id)
        if task_id in self._scheduled:
            self._scheduled.remove(task_id)
        self._completed.add(task_id)

    def detect_completion(self) -> bool:
        """Check if all tasks in the graph have completed.

        Returns:
            bool: True if completed.
        """
        return self._completed == self._all_tasks


class DependencyResolver:
    """Performs cycle checks and topological ordering over plan DAGs."""

    @staticmethod
    def get_dependencies(plan: ExecutionPlan) -> dict[str, set[str]]:
        """Compute the map of dependencies (upstream blockers) for each task.

        Returns:
            Dict[str, Set[str]]: Key is task ID, value is set of upstream dependency task IDs.
        """
        deps: dict[str, set[str]] = {node_id: set() for node_id in plan.nodes}
        for edge in plan.edges:
            if edge.to_id in deps:
                deps[edge.to_id].add(edge.from_id)
        return deps

    @staticmethod
    def get_dependents(plan: ExecutionPlan) -> dict[str, set[str]]:
        """Compute the map of dependents (downstream tasks) for each task.

        Returns:
            Dict[str, Set[str]]: Key is task ID, value is set of downstream task IDs.
        """
        dependents: dict[str, set[str]] = {node_id: set() for node_id in plan.nodes}
        for edge in plan.edges:
            if edge.from_id in dependents:
                dependents[edge.from_id].add(edge.to_id)
        return dependents

    @classmethod
    def check_cycles(cls, plan: ExecutionPlan) -> None:
        """Check for cycles in the plan. Raises SchedulerValidationError on discovery."""
        visited: dict[str, int] = {
            node_id: 0 for node_id in plan.nodes
        }  # 0=unvisited, 1=visiting, 2=visited
        deps = cls.get_dependents(plan)

        def dfs(node_id: str) -> None:
            visited[node_id] = 1
            for nxt in deps.get(node_id, set()):
                if visited[nxt] == 1:
                    raise SchedulerValidationError(
                        "Circular dependency detected in scheduler."
                    )
                if visited[nxt] == 0:
                    dfs(nxt)
            visited[node_id] = 2

        for node_id in plan.nodes:
            if visited[node_id] == 0:
                dfs(node_id)


class StageBuilder:
    """Groups task nodes into sequential execution stages matching dependency milestones."""

    @staticmethod
    def build_stages(plan: ExecutionPlan) -> list[list[str]]:
        """Compile nodes into ordered lists of parallel-eligible task stages.

        Returns:
            List[List[str]]: List of stages, each containing parallelizable task IDs.
        """
        stages: list[list[str]] = []
        deps = DependencyResolver.get_dependencies(plan)
        remaining = set(plan.nodes.keys())

        # Check for disconnected subgraphs or missing links early
        for edge in plan.edges:
            if edge.from_id not in plan.nodes or edge.to_id not in plan.nodes:
                raise SchedulerValidationError(
                    "Edge references a non-existent task node ID."
                )

        # Loop until all tasks are assigned to a stage
        while remaining:
            # Find all tasks with no remaining dependencies
            ready = []
            for node_id in remaining:
                node_deps = deps.get(node_id, set())
                # If all dependencies of this node have already been assigned to previous stages
                assigned = {task for stage in stages for task in stage}
                if node_deps.issubset(assigned):
                    ready.append(node_id)

            if not ready:
                raise SchedulerValidationError(
                    "Circular or disconnected dependency detected."
                )

            stages.append(ready)
            remaining.difference_update(ready)

        return stages


class ExecutionScheduler:
    """Validates plans, resolves depths, and compiles immutable execution schedules."""

    @staticmethod
    def create_schedule(plan: ExecutionPlan) -> ScheduleResult:
        """Validate execution plan and produce stage schedules.

        Args:
            plan: The input ExecutionPlan DAG.

        Returns:
            ScheduleResult: The compiled scheduling metadata.

        Raises:
            SchedulerValidationError: On cycle, depth overflow, or validation limits exceeded.
        """
        # 1. Validation Checks
        if not plan.nodes:
            raise SchedulerValidationError(
                "Execution plan does not contain any task nodes."
            )

        DependencyResolver.check_cycles(plan)

        # 2. Build stages
        stages = StageBuilder.build_stages(plan)

        # 3. Limit checks
        max_stages = platform_settings.SCHEDULER_MAX_STAGES
        max_depth = platform_settings.SCHEDULER_MAX_DEPTH
        max_parallel = platform_settings.SCHEDULER_MAX_PARALLEL_TASKS

        if len(stages) > max_stages:
            raise SchedulerValidationError(
                f"Schedule stage count '{len(stages)}' exceeds allowed limit '{max_stages}'."
            )
        if len(stages) > max_depth:
            raise SchedulerValidationError(
                f"Schedule execution depth '{len(stages)}' exceeds allowed limit '{max_depth}'."
            )

        actual_max_parallel = max(len(stage) for stage in stages) if stages else 0
        if actual_max_parallel > max_parallel:
            raise SchedulerValidationError(
                f"Stage parallel count '{actual_max_parallel}' exceeds allowed limit '{max_parallel}'."
            )

        # Calculate statistics
        deps = DependencyResolver.get_dependencies(plan)
        dep_count = sum(len(d) for d in deps.values())

        stats = ScheduleStatistics(
            total_tasks=len(plan.nodes),
            stage_count=len(stages),
            max_parallel_tasks=actual_max_parallel,
            critical_path_length=len(stages),
            dependency_count=dep_count,
            execution_depth=len(stages),
        )

        schedule_id = f"sch-{uuid.uuid4()}"
        return ScheduleResult(
            schedule_id=schedule_id,
            plan_id=plan.id,
            stages=stages,
            statistics=stats,
        )
