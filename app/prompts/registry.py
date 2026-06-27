"""Prompt registry module managing versioned templates."""

from app.prompts.exceptions import PromptNotFoundError
from app.prompts.template import PromptTemplate


class PromptRegistry:
    """Registry maintaining structured prompt templates by name and version."""

    def __init__(self) -> None:
        """Initialize PromptRegistry."""
        # Dict mapping: name -> (version -> PromptTemplate)
        self._templates: dict[str, dict[str, PromptTemplate]] = {}

    def register(self, template: PromptTemplate) -> None:
        """Register a versioned prompt template.

        Args:
            template: The PromptTemplate instance to register.
        """
        if template.name not in self._templates:
            self._templates[template.name] = {}
        self._templates[template.name][template.version] = template

    def get(self, name: str, version: str | None = None) -> PromptTemplate:
        """Fetch a registered template by name and version.

        If version is not provided, resolves to the latest version lexicographically.

        Args:
            name: Human-readable name of the template.
            version: Optional semantic version (e.g. '1.0.0').

        Returns:
            PromptTemplate: The requested prompt template object.

        Raises:
            PromptNotFoundError: If the name or specified version is missing.
        """
        if name not in self._templates:
            raise PromptNotFoundError(name, version)

        versions = self._templates[name]
        if not versions:
            raise PromptNotFoundError(name, version)

        if version is None:
            # Sort keys lexicographically and fetch the latest
            sorted_keys = sorted(versions.keys())
            target_version = sorted_keys[-1]
        else:
            target_version = version

        if target_version not in versions:
            raise PromptNotFoundError(name, target_version)

        return versions[target_version]

    def clear(self) -> None:
        """Clear all registered templates (utility for reset)."""
        self._templates.clear()


# Global default registry instance
registry = PromptRegistry()
