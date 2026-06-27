"""Data model representing versioned, structured prompt templates."""

from app.prompts.metadata import PromptMetadata


class PromptTemplate:
    """Structured, versioned template containing system and prompt templates."""

    def __init__(
        self,
        name: str,
        version: str,
        prompt_template: str,
        system_template: str | None = None,
        metadata: PromptMetadata | None = None,
    ) -> None:
        """Initialize PromptTemplate.

        Args:
            name: Human readable identifier name (e.g. 'schema_analysis').
            version: Semantic version string (e.g. '1.0.0').
            prompt_template: Raw Jinja2 template for user prompt content.
            system_template: Optional Jinja2 template for system instruction.
            metadata: Optional Pydantic prompt metadata object.
        """
        self.name = name
        self.version = version
        self.prompt_template = prompt_template
        self.system_template = system_template
        self.metadata = metadata
