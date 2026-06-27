"""Abstract BaseSkill definition representing standard lifecycle interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Generic

from app.skills.context import SkillContext
from app.skills.models import InputT, OutputT


class BaseSkill(ABC, Generic[InputT, OutputT]):
    """Abstract base class defining the standard lifecycle for all AI Skills."""

    name: str
    version: str
    input_schema: type[InputT]
    output_schema: type[OutputT]

    @abstractmethod
    async def validate(self, input_data: InputT, context: SkillContext) -> None:
        """Validate input parameters and context before preparation.

        Args:
            input_data: Skill-specific input parameters.
            context: Tracing and tracking metadata context.

        Raises:
            SkillValidationError: If inputs are invalid.
        """
        pass

    @abstractmethod
    async def prepare(self, input_data: InputT, context: SkillContext) -> Any:
        """Prepare internal state, resources, or prompts.

        Args:
            input_data: Skill-specific input parameters.
            context: Tracing and tracking metadata context.

        Returns:
            Any: Any prepared data needed for execution (e.g. RenderedPrompt).
        """
        pass

    @abstractmethod
    async def execute(self, prepared_data: Any, context: SkillContext) -> Any:
        """Execute the primary skill logic, interfacing with the gateway/contracts.

        Args:
            prepared_data: Prepared content returned by preparation step.
            context: Tracing and tracking metadata context.

        Returns:
            Any: Raw execution result or AIContractResponse.
        """
        pass

    @abstractmethod
    async def post_process(
        self, execution_result: Any, context: SkillContext
    ) -> OutputT:
        """Post-process results, parse outputs, and compile final output schema.

        Args:
            execution_result: Raw result returned by execution step.
            context: Tracing and tracking metadata context.

        Returns:
            O: Instantiated output model.
        """
        pass
