"""The core Workflow Engine executing ExecutionPlans topologically."""

import time
import uuid
from collections.abc import Awaitable, Callable

from app.agents.guardian.execution_plan import ExecutionPlan
from app.workflow.events import WorkflowEventEmitter
from app.workflow.exceptions import (
    WorkflowException,
    WorkflowExecutionError,
    WorkflowValidationError,
)
from app.workflow.lifecycle import WorkflowLifecycle
from app.workflow.models import (
    Workflow,
    WorkflowProgress,
    WorkflowResult,
    WorkflowState,
    WorkflowStatistics,
)
from app.workflow.progress import WorkflowProgressTracker
from app.workflow.retry import RetryPolicy
from app.workflow.scheduler import WorkflowScheduler
from app.workflow.state_machine import WorkflowStateMachine
from app.workflow.telemetry import WorkflowTelemetry


class WorkflowEngine:
    """Orchestrates plan validations, sequential transitions, progress logs, and retries."""

    def __init__(
        self, plan: ExecutionPlan, retry_policy: RetryPolicy | None = None
    ) -> None:
        """Initialize WorkflowEngine.

        Args:
            plan: The resolved ExecutionPlan.
            retry_policy: Configured retry threshold rules.
        """
        self.plan = plan
        self.retry_policy = retry_policy or RetryPolicy()
        self.workflow_id = str(uuid.uuid4())
        self.lifecycle = WorkflowLifecycle()

        # Initialize base Workflow tracking model
        self.workflow = Workflow(
            workflow_id=self.workflow_id,
            execution_id=plan.execution_id,
            state=WorkflowState.PENDING,
            progress=WorkflowProgress(total_groups=len(plan.execution_groups)),
            statistics=WorkflowStatistics(total_tables=len(plan.ordered_tables)),
            events=[],
        )
        self.progress_tracker = WorkflowProgressTracker(
            total_groups=len(plan.execution_groups)
        )
        self.scheduler = WorkflowScheduler(plan)
        self.errors: list[str] = []

    def _transition_to(self, new_state: WorkflowState, message: str) -> None:
        """Helper to move the state machine and log/emit state events."""
        old_state = self.workflow.state
        self.workflow.state = WorkflowStateMachine.transition(old_state, new_state)

        # Telemetry Structured log
        WorkflowTelemetry.log_state_transition(self.workflow_id, old_state, new_state)

        # Event tracking log
        evt = WorkflowEventEmitter.create_event(
            self.workflow_id,
            "state_transitioned",
            message,
            {"old_state": old_state.value, "new_state": new_state.value},
        )
        self.workflow.events.append(evt)

        # Trigger lifecycle hook listeners
        self.lifecycle.trigger_state_change(self.workflow_id, old_state, new_state)

    def validate_plan(self) -> None:
        """Validate execution plan parameters before scheduling execution groups.

        Raises:
            WorkflowValidationError: If required planning parameters are missing.
        """
        if not self.plan.execution_id:
            raise WorkflowValidationError("Execution plan is missing execution_id.")
        if not self.plan.ordered_tables:
            raise WorkflowValidationError("Execution plan has no ordered tables.")
        if not self.plan.execution_groups:
            raise WorkflowValidationError("Execution plan has no execution groups.")

        self._transition_to(
            WorkflowState.VALIDATED, "Execution plan validated successfully."
        )

    async def execute(
        self,
        execute_table_fn: Callable[[str], Awaitable[None]] | None = None,
    ) -> WorkflowResult:
        """Run the workflow groups sequentially in topological order.

        Args:
            execute_table_fn: Asynchronous callback simulating generation of a single table.

        Returns:
            WorkflowResult: Structured execution summary metrics.
        """
        start_time = time.perf_counter()

        self.lifecycle.trigger_start(self.workflow_id)
        WorkflowTelemetry.log_workflow_started(self.workflow_id, self.plan.execution_id)

        # Ensure validation is run if still PENDING
        if self.workflow.state == WorkflowState.PENDING:
            try:
                self.validate_plan()
            except Exception as exc:
                self._transition_to(
                    WorkflowState.FAILED, f"Plan validation failed: {exc}"
                )
                self.errors.append(f"Plan validation failed: {exc}")
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                WorkflowTelemetry.log_workflow_failure(
                    self.workflow_id, exc, duration_ms
                )
                return self._build_result()

        self._transition_to(WorkflowState.QUEUED, "Workflow queued for execution.")
        self._transition_to(WorkflowState.RUNNING, "Workflow execution started.")

        completed_groups_count = 0
        failed_groups_count = 0
        llm_calls_made = 0
        llm_cost_accumulated = 0.0

        try:
            while self.scheduler.has_more_groups():
                group = self.scheduler.next_group()
                group_str = ", ".join(group)

                evt_start = WorkflowEventEmitter.create_event(
                    self.workflow_id,
                    "group_started",
                    f"Execution group started: [{group_str}]",
                    {"group": group},
                )
                self.workflow.events.append(evt_start)

                self.workflow.progress = self.progress_tracker.update(
                    completed=completed_groups_count,
                    failed=failed_groups_count,
                    running=1,
                )
                WorkflowTelemetry.log_progress_updated(
                    self.workflow_id, self.workflow.progress
                )

                # Async runner callback mapping
                async def execute_group(g: list[str] = group) -> None:
                    if execute_table_fn:
                        for table in g:
                            await execute_table_fn(table)

                # Callback to capture retry attempt events
                def on_retry_attempt(
                    attempt: int,
                    exc: Exception,
                    g: list[str] = group,
                    g_str: str = group_str,
                ) -> None:
                    evt_retry = WorkflowEventEmitter.create_event(
                        self.workflow_id,
                        "group_retry_attempt",
                        f"Retrying execution group [{g_str}]. Attempt {attempt}/{self.retry_policy.max_retries} due to: {exc}",
                        {"group": g, "attempt": attempt, "error": str(exc)},
                    )
                    self.workflow.events.append(evt_retry)

                    # State transitions simulation (RUNNING -> RETRYING -> RUNNING)
                    old_state = self.workflow.state
                    self.workflow.state = WorkflowState.RETRYING
                    WorkflowTelemetry.log_state_transition(
                        self.workflow_id, old_state, WorkflowState.RETRYING
                    )
                    self.workflow.state = WorkflowState.RUNNING
                    WorkflowTelemetry.log_state_transition(
                        self.workflow_id, WorkflowState.RETRYING, WorkflowState.RUNNING
                    )

                try:
                    await self.retry_policy.execute_with_retry(
                        execute_group, on_retry_attempt
                    )
                    completed_groups_count += 1
                    llm_calls_made += len(group)
                    llm_cost_accumulated += len(group) * 0.005
                    self.workflow.statistics.completed_tables += len(group)

                    evt_comp = WorkflowEventEmitter.create_event(
                        self.workflow_id,
                        "group_completed",
                        f"Execution group completed successfully: [{group_str}]",
                        {"group": group},
                    )
                    self.workflow.events.append(evt_comp)

                except Exception as exc:
                    failed_groups_count += 1
                    self.workflow.statistics.failed_tables += len(group)
                    self.errors.append(f"Group [{group_str}] failed: {exc}")

                    evt_fail = WorkflowEventEmitter.create_event(
                        self.workflow_id,
                        "group_failed",
                        f"Execution group failed after retries: [{group_str}]. Error: {exc}",
                        {"group": group, "error": str(exc)},
                    )
                    self.workflow.events.append(evt_fail)

                    raise WorkflowExecutionError(
                        f"Workflow execution halted on group failure: [{group_str}] due to: {exc}"
                    ) from exc

            self._transition_to(
                WorkflowState.COMPLETED, "Workflow execution finished successfully."
            )

        except Exception as exc:
            self._transition_to(
                WorkflowState.FAILED, f"Workflow execution halted: {exc}"
            )

        # Update progress trackers
        self.workflow.progress = self.progress_tracker.update(
            completed=completed_groups_count,
            failed=failed_groups_count,
            running=0,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        self.workflow.statistics.total_duration_ms = round(duration_ms, 2)
        self.workflow.statistics.llm_calls_made = llm_calls_made
        self.workflow.statistics.llm_cost_accumulated = round(llm_cost_accumulated, 4)

        if self.workflow.state == WorkflowState.COMPLETED:
            WorkflowTelemetry.log_workflow_success(self.workflow_id, duration_ms)
        else:
            WorkflowTelemetry.log_workflow_failure(
                self.workflow_id, WorkflowException("Workflow failed"), duration_ms
            )

        self.lifecycle.trigger_complete(self.workflow_id, self.workflow.state)

        return self._build_result()

    def _build_result(self) -> WorkflowResult:
        """Consolidate current execution parameters into WorkflowResult."""
        return WorkflowResult(
            workflow_id=self.workflow_id,
            status=self.workflow.state,
            progress=self.workflow.progress,
            statistics=self.workflow.statistics,
            events=self.workflow.events,
            errors=self.errors,
        )
