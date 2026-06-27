"""Builder interface for constructing modular prompt templates from sections."""

from app.prompts.template import PromptTemplate


class PromptBuilder:
    """Builder pattern assembling structured prompts step-by-step."""

    def __init__(self) -> None:
        """Initialize PromptBuilder with empty sections."""
        self._system_instructions: str | None = None
        self._developer_instructions: list[str] = []
        self._task_instructions: list[str] = []
        self._context: list[str] = []
        self._constraints: list[str] = []
        self._safety_instructions: list[str] = []
        self._expected_output: str | None = None

    def set_system_instructions(self, text: str) -> "PromptBuilder":
        """Set the system instruction persona/constraints template.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._system_instructions = text
        return self

    def add_developer_instructions(self, text: str) -> "PromptBuilder":
        """Add developer guideline instructions.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._developer_instructions.append(text)
        return self

    def add_task_instructions(self, text: str) -> "PromptBuilder":
        """Add user task specific instructions.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._task_instructions.append(text)
        return self

    def add_context(self, text: str) -> "PromptBuilder":
        """Add dynamic variables/context details.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._context.append(text)
        return self

    def add_constraints(self, text: str) -> "PromptBuilder":
        """Add processing constraints/safety guardrails.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._constraints.append(text)
        return self

    def add_safety_instructions(self, text: str) -> "PromptBuilder":
        """Add safety guideline instructions.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._safety_instructions.append(text)
        return self

    def set_expected_output(self, text: str) -> "PromptBuilder":
        """Set the expected response output format.

        Args:
            text: Template content.

        Returns:
            PromptBuilder: self.
        """
        self._expected_output = text
        return self

    def build(self, name: str, version: str) -> PromptTemplate:
        """Compile all sections into a single unified PromptTemplate.

        Args:
            name: Human-readable name of the template.
            version: Semantic version of the template.

        Returns:
            PromptTemplate: Compiled prompt template instance.
        """
        prompt_parts = []

        if self._developer_instructions:
            prompt_parts.append("### Developer Instructions")
            prompt_parts.extend(self._developer_instructions)
            prompt_parts.append("")

        if self._task_instructions:
            prompt_parts.append("### Task Instructions")
            prompt_parts.extend(self._task_instructions)
            prompt_parts.append("")

        if self._context:
            prompt_parts.append("### Context")
            prompt_parts.extend(self._context)
            prompt_parts.append("")

        if self._constraints:
            prompt_parts.append("### Constraints")
            prompt_parts.extend(self._constraints)
            prompt_parts.append("")

        if self._safety_instructions:
            prompt_parts.append("### Safety Guidelines")
            prompt_parts.extend(self._safety_instructions)
            prompt_parts.append("")

        if self._expected_output:
            prompt_parts.append("### Expected Output")
            prompt_parts.append(self._expected_output)
            prompt_parts.append("")

        prompt_template_str = "\n".join(prompt_parts).strip()

        return PromptTemplate(
            name=name,
            version=version,
            prompt_template=prompt_template_str,
            system_template=self._system_instructions,
        )
