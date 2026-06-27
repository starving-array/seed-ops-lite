"""Strongly-typed Pydantic request models for the contract layer."""

from typing import Generic

from pydantic import BaseModel, ConfigDict, Field

from app.llm.contracts.base import T
from app.llm.models import LLMRequest
from app.prompts.models import RenderedPrompt


class AIContractRequest(BaseModel, Generic[T]):
    """Unified container for an AI Contract execution request."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    prompt: RenderedPrompt | LLMRequest = Field(
        ..., description="The rendered prompt or LLM request input."
    )
    response_schema: type[T] = Field(
        ...,
        description="The target Pydantic model class to validate the response against.",
    )
    json_mode: bool = Field(
        default=True, description="Enforce JSON mode on the gateway request."
    )
