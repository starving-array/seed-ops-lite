"""Relationships Validation Skill inspecting DDL foreign keys and cycles."""

from typing import Any

from app.llm.contracts.normalizer import AIContractNormalizer
from app.llm.contracts.request import AIContractRequest
from app.llm.gateway import LLMGateway
from app.prompts.loader import PromptAssetLoader
from app.prompts.renderer import PromptRenderer
from app.skills.base import BaseSkill
from app.skills.context import SkillContext
from app.skills.exceptions import SkillExecutionError, SkillValidationError
from app.skills.schema_validation.models import (
    RelationshipsValidationResult,
    SchemaValidationInput,
)


class RelationshipsSkill(
    BaseSkill[SchemaValidationInput, RelationshipsValidationResult]
):
    """Semantic relational review inspecting foreign key mappings and cycle Loops."""

    name = "relationships"
    version = "1.0.0"
    input_schema = SchemaValidationInput
    output_schema = RelationshipsValidationResult

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        """Initialize RelationshipsSkill.

        Args:
            gateway: Optional custom gateway instance.
        """
        self.gateway = gateway or LLMGateway()
        self.loader = PromptAssetLoader()

    async def validate(
        self, input_data: SchemaValidationInput, _context: SkillContext
    ) -> None:
        """Validate input parameters.

        Args:
            input_data: DDL input container.
            _context: Skill context tracking.
        """
        if not input_data.schema_ddl.strip():
            raise SkillValidationError("Schema DDL cannot be empty.")

    async def prepare(
        self, input_data: SchemaValidationInput, _context: SkillContext
    ) -> Any:
        """Load and render relationships prompt template.

        Args:
            input_data: DDL input container.
            _context: Skill context tracking.

        Returns:
            RenderedPrompt: Deterministically rendered prompt data.
        """
        template = self.loader.load_prompt(self.name)
        return PromptRenderer.render(template, {"schema_ddl": input_data.schema_ddl})

    async def execute(self, prepared_data: Any, _context: SkillContext) -> Any:
        """Execute model generation via AI Contract Layer.

        Args:
            prepared_data: Rendered prompt data.
            _context: Skill context tracking.

        Returns:
            AIContractResponse: Standardized outcome details.
        """
        contract_request = AIContractRequest[RelationshipsValidationResult](
            prompt=prepared_data,
            response_schema=self.output_schema,
            json_mode=True,
        )
        return await AIContractNormalizer.execute_contract(
            self.gateway, contract_request
        )

    async def post_process(
        self, execution_result: Any, _context: SkillContext
    ) -> RelationshipsValidationResult:
        """Resolve and extract final output models.

        Args:
            execution_result: AIContractResponse from gateway.
            context: Skill context tracking.

        Returns:
            RelationshipsValidationResult: Validated Pydantic model.
        """
        if not execution_result.success:
            raise SkillExecutionError(
                f"Relationships Skill contract execution failed: {execution_result.error.message if execution_result.error else 'Unknown error'}"
            )
        from typing import cast

        return cast(RelationshipsValidationResult, execution_result.data)
