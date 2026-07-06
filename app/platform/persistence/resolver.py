import contextvars

_active_project_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "active_project_id", default="default"
)


class ProjectResolver:
    """Central resolver for active projects and compatibility contexts."""

    DEFAULT_PROJECT_ID = "default"

    @classmethod
    def get_active_project_id(cls) -> str:
        """Resolve the active project ID for SafeSeedOps Lite."""
        return _active_project_id.get()

    @classmethod
    def set_active_project_id(cls, project_id: str) -> None:
        """Set the active project ID in the current async context."""
        _active_project_id.set(project_id)
