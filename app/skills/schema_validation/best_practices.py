"""Best Practices Validation Skill inspecting DDL indexes and performance strategy."""

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
    BestPracticesValidationResult,
    SchemaValidationInput,
)


class BestPracticesSkill(
    BaseSkill[SchemaValidationInput, BestPracticesValidationResult]
):
    """Semantic performance review inspecting indexing, maintainability, and scalability."""

    name = "best_practices"
    version = "1.0.0"
    input_schema = SchemaValidationInput
    output_schema = BestPracticesValidationResult

    def __init__(self, gateway: LLMGateway | None = None) -> None:
        """Initialize BestPracticesSkill.

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
        """Load and render best practices prompt template.

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
        contract_request = AIContractRequest[BestPracticesValidationResult](
            prompt=prepared_data,
            response_schema=self.output_schema,
            json_mode=True,
        )
        return await AIContractNormalizer.execute_contract(
            self.gateway, contract_request
        )

    async def post_process(
        self, execution_result: Any, _context: SkillContext
    ) -> BestPracticesValidationResult:
        """Resolve and extract final output models.

        Args:
            execution_result: AIContractResponse from gateway.
            context: Skill context tracking.

        Returns:
            BestPracticesValidationResult: Validated Pydantic model.
        """
        if not execution_result.success:
            raise SkillExecutionError(
                f"Best Practices Skill contract execution failed: {execution_result.error.message if execution_result.error else 'Unknown error'}"
            )
        from typing import cast

        return cast(BestPracticesValidationResult, execution_result.data)
