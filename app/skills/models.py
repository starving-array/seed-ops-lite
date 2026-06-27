"""Strongly-typed Pydantic request and response models for skills."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

from app.skills.context import SkillContext

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class SkillRequest(BaseModel, Generic[InputT]):
    """Generic request structure wrapping input parameters and skill execution context."""

    input_data: InputT = Field(..., description="Skill-specific input parameters.")
    context: SkillContext = Field(
        default_factory=SkillContext, description="Execution tracing context."
    )


class SkillResponse(BaseModel, Generic[OutputT]):
    """Generic response structure wrapping output data, latency, and success status."""

    success: bool = Field(
        ..., description="Indicates if the skill executed successfully."
    )
    data: OutputT | None = Field(
        default=None, description="Skill-specific output model data."
    )
    error_message: str | None = Field(
        default=None, description="Details of the error if success is False."
    )
    latency_ms: float = Field(
        default=0.0, description="Total execution time in milliseconds."
    )
