"""Helper tracking and computing measured workflow execution progress metrics."""

from app.workflow.models import WorkflowProgress


class WorkflowProgressTracker:
    """Manages active progress counters and computes completion ratios."""

    def __init__(self, total_groups: int) -> None:
        """Initialize progress tracker with total groups count."""
        self.total_groups = total_groups
        self.completed_groups = 0
        self.failed_groups = 0
        self.running_groups = 0

    def update(self, completed: int, failed: int, running: int) -> WorkflowProgress:
        """Update state counters and recalculate metrics.

        Args:
            completed: Number of completed groups.
            failed: Number of failed groups.
            running: Number of active running groups.

        Returns:
            WorkflowProgress: Recalculated progress model.
        """
        self.completed_groups = completed
        self.failed_groups = failed
        self.running_groups = running
        return self.get_progress()

    def get_progress(self) -> WorkflowProgress:
        """Calculate percentage and return a WorkflowProgress snapshot.

        Returns:
            WorkflowProgress: Current progress metrics.
        """
        pct = 0.0
        if self.total_groups > 0:
            pct = round((self.completed_groups / self.total_groups) * 100.0, 2)
        return WorkflowProgress(
            total_groups=self.total_groups,
            completed_groups=self.completed_groups,
            failed_groups=self.failed_groups,
            running_groups=self.running_groups,
            progress_percentage=pct,
        )
