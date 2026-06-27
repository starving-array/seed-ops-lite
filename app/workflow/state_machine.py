from typing import ClassVar

from app.workflow.exceptions import InvalidStateTransitionError
from app.workflow.models import WorkflowState


class WorkflowStateMachine:
    """Governs state transitions for execution workflows, rejecting invalid paths."""

    # Map of source state to set of allowed destination states
    ALLOWED_TRANSITIONS: ClassVar[dict[WorkflowState, set[WorkflowState]]] = {
        WorkflowState.PENDING: {
            WorkflowState.VALIDATED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.VALIDATED: {
            WorkflowState.QUEUED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.QUEUED: {
            WorkflowState.RUNNING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.RUNNING: {
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.RETRYING,
            WorkflowState.PAUSED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.RETRYING: {
            WorkflowState.RUNNING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.PAUSED: {
            WorkflowState.RUNNING,
            WorkflowState.CANCELLED,
        },
        WorkflowState.COMPLETED: set(),
        WorkflowState.FAILED: set(),
        WorkflowState.CANCELLED: set(),
    }

    @classmethod
    def transition(
        cls, current_state: WorkflowState, target_state: WorkflowState
    ) -> WorkflowState:
        """Validate and apply a transition from current_state to target_state.

        Args:
            current_state: The active workflow state.
            target_state: The requested state transition destination.

        Returns:
            WorkflowState: The updated workflow state.

        Raises:
            InvalidStateTransitionError: If the transition path is invalid.
        """
        # If target state matches current state, it is a no-op
        if current_state == target_state:
            return current_state

        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, set())
        if target_state not in allowed:
            raise InvalidStateTransitionError(
                f"Invalid state transition: Cannot move from '{current_state.value}' "
                f"to '{target_state.value}'."
            )

        return target_state
