"""ExecutionStateMachine enforcing lifecycle validation rules and state transitions."""

from typing import ClassVar

from app.agents.execution.models import ExecutionState


class InvalidStateTransitionError(Exception):
    """Exception raised when an invalid state machine transition is attempted."""

    pass


class ExecutionStateMachine:
    """State machine validator enforcing the agent execution lifecycle."""

    # Map of valid next states for each current state
    _VALID_TRANSITIONS: ClassVar[dict[ExecutionState, set[ExecutionState]]] = {
        ExecutionState.CREATED: {
            ExecutionState.INITIALIZED,
            ExecutionState.CANCELLED,
        },
        ExecutionState.INITIALIZED: {
            ExecutionState.QUEUED,
            ExecutionState.RUNNING,
            ExecutionState.CANCELLED,
        },
        ExecutionState.QUEUED: {
            ExecutionState.RUNNING,
            ExecutionState.CANCELLED,
        },
        ExecutionState.RUNNING: {
            ExecutionState.WAITING,
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        },
        ExecutionState.WAITING: {
            ExecutionState.RUNNING,
            ExecutionState.CANCELLED,
            ExecutionState.FAILED,
        },
        ExecutionState.RECOVERED: {
            ExecutionState.INITIALIZED,
            ExecutionState.QUEUED,
            ExecutionState.RUNNING,
        },
        # Terminal states: no valid next states allowed
        ExecutionState.COMPLETED: set(),
        ExecutionState.FAILED: set(),
        ExecutionState.CANCELLED: set(),
    }

    @classmethod
    def validate_transition(
        cls, current: ExecutionState, target: ExecutionState
    ) -> None:
        """Validate if a transition from current state to target state is legally allowed.

        Args:
            current: The starting ExecutionState.
            target: The target ExecutionState to transition into.

        Raises:
            InvalidStateTransitionError: If the transition is prohibited.
        """
        # If current is same as target, transition is a no-op (valid)
        if current == target:
            return

        valid_targets = cls._VALID_TRANSITIONS.get(current, set())
        if target not in valid_targets:
            raise InvalidStateTransitionError(
                f"Prohibited transition: cannot transition from state '{current.value}' to '{target.value}'."
            )

    @classmethod
    def is_terminal(cls, state: ExecutionState) -> bool:
        """Verify if a given execution state is terminal.

        Args:
            state: Target ExecutionState.

        Returns:
            bool: True if state is Completed, Failed, or Cancelled.
        """
        return state in {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
        }
