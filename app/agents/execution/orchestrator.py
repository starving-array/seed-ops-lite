"""Agent Execution Orchestrator coordinating Scheduler, AgentManager, and ReadyQueue."""

import time
import uuid
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.execution.models import (
    ExecutionCancelled,
    ExecutionCompleted,
    ExecutionContext,
    ExecutionEvent,
    ExecutionFailed,
    ExecutionMetadata,
    ExecutionResult,
    ExecutionSession,
    ExecutionStarted,
    ExecutionState,
    ExecutionStatistics,
    ExecutionTimeline,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
)
from app.agents.execution.scheduler import ExecutionScheduler, ReadyQueue
from app.agents.execution.state_machine import ExecutionStateMachine
from app.agents.framework.manager import AgentManager
from app.agents.planning.models import ExecutionPlan
from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.telemetry.events import EventID


class ExecutionSummary(BaseModel):
    """Immutable compiled final result summary for an orchestrated execution session."""

    model_config = ConfigDict(frozen=True)

    success: bool
    session_id: str
    state: ExecutionState
    task_outputs: dict[str, Any] = Field(default_factory=dict)
    statistics: ExecutionStatistics = Field(default_factory=ExecutionStatistics)
    timeline: ExecutionTimeline = Field(default_factory=ExecutionTimeline)
    error_message: str | None = Field(default=None)


class ExecutionEventDispatcher:
    """Manages subscription and publishing of execution lifecycle event models."""

    def __init__(self) -> None:
        self._listeners: list[Callable[[ExecutionEvent], None]] = []

    def subscribe(self, listener: Callable[[ExecutionEvent], None]) -> None:
        """Register a subscriber callback for execution events."""
        self._listeners.append(listener)

    def publish(self, event: ExecutionEvent) -> None:
        """Deliver an execution event to all active subscribers."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as exc:
                logger.error(
                    EventID.LOG_ERROR,
                    f"Failed to publish event to subscriber: {exc}",
                    component="ExecutionEventDispatcher",
                )


class ExecutionSessionManager:
    """Tracks active sessions, validating concurrency limits using PlatformSettings."""

    def __init__(self) -> None:
        self._sessions: dict[str, ExecutionSession] = {}

    def create_session(
        self,
        session_id: str,
        execution_id: str,
        context: ExecutionContext,
        _metadata: ExecutionMetadata | None = None,
    ) -> ExecutionSession:
        """Instantiate and record a new active execution session.

        Raises:
            ValueError: If session ID already exists or limits are exceeded.
        """
        limit = platform_settings.ORCHESTRATOR_MAX_ACTIVE_SESSIONS
        if len(self._sessions) >= limit:
            raise ValueError(f"Max active session limit '{limit}' exceeded.")

        if session_id in self._sessions:
            raise ValueError(f"Session with ID '{session_id}' already exists.")

        session = ExecutionSession(
            session_id=session_id,
            execution_id=execution_id,
            context=context,
            state=ExecutionState.CREATED,
            timeline=ExecutionTimeline(),
            statistics=ExecutionStatistics(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ExecutionSession | None:
        """Fetch active session by identification ID."""
        return self._sessions.get(session_id)

    def update_session(self, session: ExecutionSession) -> None:
        """Update session record in local storage."""
        self._sessions[session.session_id] = session

    def remove_session(self, session_id: str) -> None:
        """Delete session from active tracking."""
        if session_id in self._sessions:
            del self._sessions[session_id]


class TaskDispatcher:
    """Dispatches execution nodes through the AgentManager framework."""

    def __init__(self, agent_manager: AgentManager) -> None:
        self.agent_manager = agent_manager

    async def dispatch_task(
        self,
        node_id: str,  # noqa: ARG002
        inputs: dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        """Trigger target task executor block via AgentManager.

        Args:
            node_id: Target task node ID.
            inputs: User variables or task properties.
            context: Scoped execution context variables.

        Returns:
            Any: Return execution outputs dictionary.
        """
        # Tasks are routed strictly through the AgentManager
        # Since we're in read-only / deterministic mode and shouldn't execute
        # arbitrary tools, we delegate validation and run orchestration to execute_agent.
        return await self.agent_manager.execute_agent(
            agent_id=context.agent_id,
            inputs=inputs,
            variables=context.variables,
            workflow_id=context.workflow_id,
            workflow_version=context.workflow_version,
        )


class ExecutionCoordinator:
    """Runs orchestrated loops across schedules, dispatches nodes, and handles cancellations."""

    def __init__(
        self,
        session_manager: ExecutionSessionManager,
        event_dispatcher: ExecutionEventDispatcher,
        task_dispatcher: TaskDispatcher,
    ) -> None:
        self.session_manager = session_manager
        self.event_dispatcher = event_dispatcher
        self.task_dispatcher = task_dispatcher
        self._metrics = {
            "sessions_created": 0,
            "tasks_dispatched": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_duration": 0.0,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Retrieve telemetry metrics summary from current runs."""
        return dict(self._metrics)

    async def execute_plan(
        self,
        session_id: str,
        plan: ExecutionPlan,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> ExecutionSummary:
        """Coordinate execution stages of a plan schedule until terminal states are reached.

        Args:
            session_id: Active session to pull.
            plan: Core compiled ExecutionPlan.
            cancellation_check: Optional hook returning True if cancellation requested.

        Returns:
            ExecutionSummary: Summary outcomes payload.
        """
        start_time = time.perf_counter()
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Execution session '{session_id}' not found.")

        # Update transition to Initialized
        ExecutionStateMachine.validate_transition(
            session.state, ExecutionState.INITIALIZED
        )
        session = ExecutionSession(
            session_id=session.session_id,
            execution_id=session.execution_id,
            context=session.context,
            state=ExecutionState.INITIALIZED,
            timeline=ExecutionTimeline(
                created_at=session.timeline.created_at, started_at=time.time()
            ),
        )
        self.session_manager.update_session(session)

        # 1. Load Schedule
        try:
            schedule = ExecutionScheduler.create_schedule(plan)
        except Exception as exc:
            # Transition to Failed
            ExecutionStateMachine.validate_transition(
                session.state, ExecutionState.FAILED
            )
            session = ExecutionSession(
                session_id=session.session_id,
                execution_id=session.execution_id,
                context=session.context,
                state=ExecutionState.FAILED,
                timeline=ExecutionTimeline(
                    created_at=session.timeline.created_at,
                    started_at=session.timeline.started_at,
                    completed_at=time.time(),
                ),
                result=ExecutionResult(success=False, error_message=str(exc)),
            )
            self.session_manager.update_session(session)
            self._metrics["tasks_failed"] += len(plan.nodes)
            return ExecutionSummary(
                success=False,
                session_id=session_id,
                state=session.state,
                error_message=str(exc),
                statistics=session.statistics,
                timeline=session.timeline,
            )

        # Update state to Running
        ExecutionStateMachine.validate_transition(session.state, ExecutionState.RUNNING)
        session = ExecutionSession(
            session_id=session.session_id,
            execution_id=session.execution_id,
            context=session.context,
            state=ExecutionState.RUNNING,
            timeline=session.timeline,
            statistics=ExecutionStatistics(task_count=len(plan.nodes)),
        )
        self.session_manager.update_session(session)

        self._metrics["sessions_created"] += 1
        self.event_dispatcher.publish(
            ExecutionStarted(
                event_id=str(uuid.uuid4()),
                execution_id=session.execution_id,
                workflow_id=session.context.workflow_id,
                agent_id=session.context.agent_id,
            )
        )

        task_outputs: dict[str, Any] = {}
        deps = {
            edge.to_id: {edge.from_id} for edge in plan.edges
        }  # Simple dependencies
        for node_id in plan.nodes:
            if node_id not in deps:
                deps[node_id] = set()

        queue = ReadyQueue(schedule.stages, deps)

        # Process Stages
        try:
            for stage in schedule.stages:
                if cancellation_check and cancellation_check():
                    raise InterruptedError("Cancellation requested.")

                # Dispatch tasks in current stage (Parallelizable)
                for task_id in stage:
                    if cancellation_check and cancellation_check():
                        raise InterruptedError("Cancellation requested.")

                    queue.push_ready(task_id)
                    self._metrics["tasks_dispatched"] += 1
                    self.event_dispatcher.publish(
                        TaskStarted(
                            event_id=str(uuid.uuid4()),
                            execution_id=session.execution_id,
                            workflow_id=session.context.workflow_id,
                            agent_id=session.context.agent_id,
                            task_id=task_id,
                            node_id=task_id,
                        )
                    )

                    # Simulate agent task run
                    task_start_time = time.perf_counter()
                    node = plan.nodes[task_id]
                    inputs = {"node_id": node.id, "title": node.title}
                    res = await self.task_dispatcher.dispatch_task(
                        node_id=task_id,
                        inputs=inputs,
                        context=session.context,
                    )

                    duration = time.perf_counter() - task_start_time
                    if hasattr(res, "errors") and res.errors:
                        # Fail task
                        self._metrics["tasks_failed"] += 1
                        self.event_dispatcher.publish(
                            TaskFailed(
                                event_id=str(uuid.uuid4()),
                                execution_id=session.execution_id,
                                workflow_id=session.context.workflow_id,
                                agent_id=session.context.agent_id,
                                task_id=task_id,
                                node_id=task_id,
                                error=res.errors[0],
                                duration=duration,
                            )
                        )
                        raise ValueError(f"Task '{task_id}' failed: {res.errors[0]}")

                    # Complete task
                    queue.start_task(task_id)
                    queue.remove_completed(task_id)
                    task_outputs[task_id] = getattr(res, "outputs", {})
                    self._metrics["tasks_completed"] += 1
                    self.event_dispatcher.publish(
                        TaskCompleted(
                            event_id=str(uuid.uuid4()),
                            execution_id=session.execution_id,
                            workflow_id=session.context.workflow_id,
                            agent_id=session.context.agent_id,
                            task_id=task_id,
                            node_id=task_id,
                            duration=duration,
                        )
                    )

            # Execution complete
            duration = time.perf_counter() - start_time
            self._metrics["total_duration"] += duration

            stats = ExecutionStatistics(
                task_count=len(plan.nodes),
                completed_count=len(plan.nodes),
                execution_duration=duration,
            )

            ExecutionStateMachine.validate_transition(
                session.state, ExecutionState.COMPLETED
            )
            res_val = ExecutionResult(
                success=True, outputs=task_outputs, statistics=stats
            )
            session = ExecutionSession(
                session_id=session.session_id,
                execution_id=session.execution_id,
                context=session.context,
                state=ExecutionState.COMPLETED,
                timeline=ExecutionTimeline(
                    created_at=session.timeline.created_at,
                    started_at=session.timeline.started_at,
                    completed_at=time.time(),
                ),
                statistics=stats,
                result=res_val,
            )
            self.session_manager.update_session(session)

            self.event_dispatcher.publish(
                ExecutionCompleted(
                    event_id=str(uuid.uuid4()),
                    execution_id=session.execution_id,
                    workflow_id=session.context.workflow_id,
                    agent_id=session.context.agent_id,
                    result=res_val,
                )
            )

            return ExecutionSummary(
                success=True,
                session_id=session_id,
                state=session.state,
                task_outputs=task_outputs,
                statistics=stats,
                timeline=session.timeline,
            )

        except InterruptedError as exc:
            # Cancellation handling
            duration = time.perf_counter() - start_time
            stats = ExecutionStatistics(
                task_count=len(plan.nodes),
                skipped_count=len(plan.nodes) - len(task_outputs),
                execution_duration=duration,
            )
            ExecutionStateMachine.validate_transition(
                session.state, ExecutionState.CANCELLED
            )
            res_val = ExecutionResult(
                success=False, error_message=str(exc), statistics=stats
            )
            session = ExecutionSession(
                session_id=session.session_id,
                execution_id=session.execution_id,
                context=session.context,
                state=ExecutionState.CANCELLED,
                timeline=ExecutionTimeline(
                    created_at=session.timeline.created_at,
                    started_at=session.timeline.started_at,
                    completed_at=time.time(),
                ),
                statistics=stats,
                result=res_val,
            )
            self.session_manager.update_session(session)

            self.event_dispatcher.publish(
                ExecutionCancelled(
                    event_id=str(uuid.uuid4()),
                    execution_id=session.execution_id,
                    workflow_id=session.context.workflow_id,
                    agent_id=session.context.agent_id,
                    reason=str(exc),
                    result=res_val,
                )
            )

            return ExecutionSummary(
                success=False,
                session_id=session_id,
                state=session.state,
                error_message=str(exc),
                statistics=stats,
                timeline=session.timeline,
            )

        except Exception as exc:
            # General failure propagation
            duration = time.perf_counter() - start_time
            stats = ExecutionStatistics(
                task_count=len(plan.nodes),
                failed_count=1,
                completed_count=len(task_outputs),
                execution_duration=duration,
            )
            ExecutionStateMachine.validate_transition(
                session.state, ExecutionState.FAILED
            )
            res_val = ExecutionResult(
                success=False, error_message=str(exc), statistics=stats
            )
            session = ExecutionSession(
                session_id=session.session_id,
                execution_id=session.execution_id,
                context=session.context,
                state=ExecutionState.FAILED,
                timeline=ExecutionTimeline(
                    created_at=session.timeline.created_at,
                    started_at=session.timeline.started_at,
                    completed_at=time.time(),
                ),
                statistics=stats,
                result=res_val,
            )
            self.session_manager.update_session(session)

            self.event_dispatcher.publish(
                ExecutionFailed(
                    event_id=str(uuid.uuid4()),
                    execution_id=session.execution_id,
                    workflow_id=session.context.workflow_id,
                    agent_id=session.context.agent_id,
                    error=str(exc),
                    result=res_val,
                )
            )

            return ExecutionSummary(
                success=False,
                session_id=session_id,
                state=session.state,
                error_message=str(exc),
                statistics=stats,
                timeline=session.timeline,
            )


class ExecutionOrchestrator:
    """Orchestrates execution sessions and coordinates planners and schedulers."""

    def __init__(self, coordinator: ExecutionCoordinator) -> None:
        self.coordinator = coordinator

    async def execute_plan(
        self,
        session_id: str,
        plan: ExecutionPlan,
        cancellation_check: Callable[[], bool] | None = None,
    ) -> ExecutionSummary:
        """Forward plan execution requests to the underlying coordinator coordinator loop."""
        return await self.coordinator.execute_plan(session_id, plan, cancellation_check)
