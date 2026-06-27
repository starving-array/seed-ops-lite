"""Registry maintaining active AI skill instances by name and semantic version."""

from typing import Any

from app.skills.base import BaseSkill
from app.skills.exceptions import SkillNotFoundError


class SkillRegistry:
    """Registry maintaining active AI skill instances by name and semantic version."""

    def __init__(self) -> None:
        self._skills: dict[tuple[str, str], BaseSkill[Any, Any]] = {}

    def register(self, skill: BaseSkill[Any, Any]) -> None:
        """Register a skill instance.

        Args:
            skill: An instantiated BaseSkill.
        """
        key = (skill.name.lower(), skill.version)
        self._skills[key] = skill

    def get(self, name: str, version: str) -> BaseSkill[Any, Any]:
        """Resolve and retrieve a registered skill.

        Args:
            name: The unique skill name.
            version: The exact semantic version string.

        Returns:
            BaseSkill[Any, Any]: Resolved skill instance.

        Raises:
            SkillNotFoundError: If name/version combination is not registered.
        """
        key = (name.lower(), version)
        if key not in self._skills:
            raise SkillNotFoundError(
                f"Skill '{name}' (version {version}) is not registered."
            )
        return self._skills[key]

    def clear(self) -> None:
        """Clear all registered skills (primarily for testing)."""
        self._skills.clear()


# Global registry instance
registry = SkillRegistry()
