"""Planner class responsible for determining which schema validation skills to run."""

from typing import Any

from app.agents.schema_validation.exceptions import PlannerException
from app.skills.base import BaseSkill
from app.skills.registry import registry


class SchemaValidationPlanner:
    """Planner deciding which validation skills to run based on registered skills."""

    def __init__(self, skill_names: list[str] | None = None) -> None:
        """Initialize the planner with optional custom skill names to run."""
        self.skill_names = skill_names or [
            "structure",
            "relationships",
            "naming",
            "data_quality",
            "best_practices",
        ]

    def plan(self) -> list[BaseSkill[Any, Any]]:
        """Generate an execution plan consisting of registered validation skills.

        Returns:
            List[BaseSkill]: A list of skill instances to execute.

        Raises:
            PlannerException: If a required skill cannot be resolved or is not registered.
        """
        execution_plan: list[BaseSkill[Any, Any]] = []
        for name in self.skill_names:
            try:
                skill = registry.get(name, "1.0.0")
                execution_plan.append(skill)
            except Exception as exc:
                raise PlannerException(
                    f"Failed to resolve validation skill '{name}' (version 1.0.0): {exc}"
                ) from exc
        return execution_plan
