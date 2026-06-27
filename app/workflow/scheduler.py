"""Deterministic scheduler traversing execution plan layers topologically."""

from app.agents.guardian.execution_plan import ExecutionPlan


class WorkflowScheduler:
    """Traverses table execution layers topologically in parallel groups."""

    def __init__(self, plan: ExecutionPlan) -> None:
        """Initialize WorkflowScheduler with an ExecutionPlan.

        Args:
            plan: The resolved ExecutionPlan from the Guardian Planner.
        """
        self.plan = plan
        self.groups: list[list[str]] = plan.execution_groups
        self.current_group_index = 0

    def has_more_groups(self) -> bool:
        """Check if there are remaining execution groups to run.

        Returns:
            bool: True if there are groups left to schedule.
        """
        return self.current_group_index < len(self.groups)

    def next_group(self) -> list[str]:
        """Advance index and return the next parallel group of table names.

        Returns:
            List[str]: Table names in the next execution layer.

        Raises:
            IndexError: If all groups have already been scheduled.
        """
        if not self.has_more_groups():
            raise IndexError("No more execution groups remaining in the plan.")
        group = self.groups[self.current_group_index]
        self.current_group_index += 1
        return group
