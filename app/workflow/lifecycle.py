"""Execution lifecycle hooks and event handlers for the Workflow Engine."""

import contextlib
from collections.abc import Callable

from app.workflow.models import WorkflowState


class WorkflowLifecycle:
    """Publishes state change triggers and registers callback hooks."""

    def __init__(self) -> None:
        """Initialize WorkflowLifecycle."""
        self._on_start_listeners: list[Callable[[str], None]] = []
        self._on_state_change_listeners: list[
            Callable[[str, WorkflowState, WorkflowState], None]
        ] = []
        self._on_complete_listeners: list[Callable[[str, WorkflowState], None]] = []

    def register_on_start(self, callback: Callable[[str], None]) -> None:
        """Register start lifecycle hook callback."""
        self._on_start_listeners.append(callback)

    def register_on_state_change(
        self, callback: Callable[[str, WorkflowState, WorkflowState], None]
    ) -> None:
        """Register state change lifecycle hook callback."""
        self._on_state_change_listeners.append(callback)

    def register_on_complete(
        self, callback: Callable[[str, WorkflowState], None]
    ) -> None:
        """Register workflow completion lifecycle hook callback."""
        self._on_complete_listeners.append(callback)

    def trigger_start(self, workflow_id: str) -> None:
        """Fire event when workflow starts."""
        for listener in self._on_start_listeners:
            with contextlib.suppress(Exception):
                listener(workflow_id)

    def trigger_state_change(
        self, workflow_id: str, old_state: WorkflowState, new_state: WorkflowState
    ) -> None:
        """Fire event when workflow transitions states."""
        for listener in self._on_state_change_listeners:
            with contextlib.suppress(Exception):
                listener(workflow_id, old_state, new_state)

    def trigger_complete(self, workflow_id: str, final_state: WorkflowState) -> None:
        """Fire event when workflow completes or fails."""
        for listener in self._on_complete_listeners:
            with contextlib.suppress(Exception):
                listener(workflow_id, final_state)
