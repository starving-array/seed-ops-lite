"""Asset loader for YAML metadata and Markdown prompt templates."""

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from app.prompts.builder import PromptBuilder
from app.prompts.exceptions import (
    PromptNotFoundError,
    PromptTemplateError,
    PromptValidationError,
)
from app.prompts.metadata import PromptMetadata
from app.prompts.template import PromptTemplate

DEFAULT_TEMPLATES_DIR = Path(__file__).parent / "templates"


class PromptAssetLoader:
    """Loader managing prompt file assets and inheritance."""

    def __init__(self, templates_dir: Path | str | None = None) -> None:
        """Initialize PromptAssetLoader.

        Args:
            templates_dir: Base directory path containing template folders.
        """
        self.templates_dir = Path(templates_dir or DEFAULT_TEMPLATES_DIR)

    def load_metadata(self, agent_name: str) -> PromptMetadata:
        """Load and validate Pydantic metadata from metadata.yaml.

        Args:
            agent_name: Name of the agent subdirectory.

        Returns:
            PromptMetadata: Validated Pydantic metadata.

        Raises:
            PromptNotFoundError: If metadata.yaml does not exist.
            PromptTemplateError: If YAML formatting is malformed.
            PromptValidationError: If Pydantic validation fails.
        """
        metadata_path = self.templates_dir / agent_name / "metadata.yaml"
        if not metadata_path.exists():
            raise PromptNotFoundError(agent_name, "metadata.yaml missing")

        try:
            with metadata_path.open(encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        except Exception as exc:
            raise PromptTemplateError(
                f"Failed to parse malformed YAML in {metadata_path}: {exc}"
            ) from exc

        try:
            return PromptMetadata(**raw_data)
        except ValidationError as exc:
            raise PromptValidationError(
                f"Validation failed for prompt metadata in {metadata_path}: {exc}",
                details={"errors": exc.errors()},
            ) from exc

    def _read_file_or_fallback(
        self, agent_dir: Path, common_dir: Path, filename: str
    ) -> str | None:
        """Read file from agent directory or fallback to common directory.

        Args:
            agent_dir: Agent specific template directory.
            common_dir: Common shared template directory.
            filename: Target file name to read.

        Returns:
            str | None: String content of the file or None if it doesn't exist.
        """
        agent_file = agent_dir / filename
        if agent_file.exists():
            return agent_file.read_text(encoding="utf-8").strip()

        common_file = common_dir / filename
        if common_file.exists():
            return common_file.read_text(encoding="utf-8").strip()

        return None

    def load_prompt(self, agent_name: str) -> PromptTemplate:
        """Load, inherit, and build a unified prompt template from file assets.

        Args:
            agent_name: Name of the agent subdirectory.

        Returns:
            PromptTemplate: Compiled prompt template instance.
        """
        metadata = self.load_metadata(agent_name)
        agent_dir = self.templates_dir / agent_name
        common_dir = self.templates_dir / "common"

        # 1. Load System instructions (with override option)
        system_text = self._read_file_or_fallback(agent_dir, common_dir, "system.md")

        # 2. Load Constraints (with override option)
        constraints_text = self._read_file_or_fallback(
            agent_dir, common_dir, "constraints.md"
        )

        # 3. Load Expected output format (with override option)
        output_format_text = self._read_file_or_fallback(
            agent_dir, common_dir, "output_format.md"
        )

        # Load Safety instructions (with override option)
        safety_text = self._read_file_or_fallback(agent_dir, common_dir, "safety.md")

        # 4. Load Developer guidelines
        dev_file = agent_dir / "developer.md"
        dev_text = (
            dev_file.read_text(encoding="utf-8").strip() if dev_file.exists() else None
        )

        # 5. Load Task instructions
        task_file = agent_dir / "task.md"
        task_text = (
            task_file.read_text(encoding="utf-8").strip()
            if task_file.exists()
            else None
        )

        # Assemble compiled template using PromptBuilder
        builder = PromptBuilder()

        if system_text:
            builder.set_system_instructions(system_text)
        if dev_text:
            builder.add_developer_instructions(dev_text)
        if task_text:
            builder.add_task_instructions(task_text)
        if constraints_text:
            builder.add_constraints(constraints_text)
        if safety_text:
            builder.add_safety_instructions(safety_text)
        if output_format_text:
            builder.set_expected_output(output_format_text)

        # Build prompt template
        template = builder.build(metadata.name, metadata.version)
        template.metadata = metadata

        return template
