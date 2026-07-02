class ProjectResolver:
    """Central resolver for active projects and compatibility contexts."""

    DEFAULT_PROJECT_ID = "default"

    @classmethod
    def get_active_project_id(cls) -> str:
        """Resolve the active project ID for SafeSeedOps Lite."""
        return cls.DEFAULT_PROJECT_ID
