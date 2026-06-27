"""Factory helper for emitting and formatting structured workflow events."""

import uuid
from datetime import UTC, datetime
from typing import Any

from app.workflow.models import WorkflowEvent


class WorkflowEventEmitter:
    """Helper producing strongly-typed WorkflowEvent structures."""

    @staticmethod
    def create_event(
        workflow_id: str,
        event_type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> WorkflowEvent:
        """Create a new WorkflowEvent with standard UUID and timezone-aware timestamp.

        Args:
            workflow_id: Target workflow UUID.
            event_type: Event categorization category name.
            message: Informational description.
            metadata: Contextual data dictionary.

        Returns:
            WorkflowEvent: Populated event model.
        """
        return WorkflowEvent(
            event_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            timestamp=datetime.now(UTC).isoformat(),
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )
