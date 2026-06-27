"""Unit tests for the Skill Framework validating registration, lifecycle execution, and error handling."""

from typing import Any

import pytest
from pydantic import BaseModel

from app.skills.base import BaseSkill
from app.skills.context import SkillContext
from app.skills.exceptions import (
    SkillNotFoundError,
    SkillValidationError,
)
from app.skills.executor import SkillExecutor
from app.skills.models import SkillRequest
from app.skills.registry import registry


# Schema Definitions
class DummyInput(BaseModel):
    value: int


class DummyOutput(BaseModel):
    doubled_value: int


# Test Skill Implementations
class DummySkill(BaseSkill[DummyInput, DummyOutput]):
    """Standard dummy skill for checking normal execution flow."""

    name = "dummy"
    version = "1.0.0"
    input_schema = DummyInput
    output_schema = DummyOutput

    async def validate(self, input_data: DummyInput, _context: SkillContext) -> None:
        if input_data.value < 0:
            raise SkillValidationError("Value cannot be negative.")

    async def prepare(self, input_data: DummyInput, _context: SkillContext) -> Any:
        if input_data.value == 999:
            raise ValueError("Prepare crash")
        return input_data.value * 2

    async def execute(self, prepared_data: Any, _context: SkillContext) -> Any:
        if prepared_data == 888 * 2:
            raise ValueError("Execute crash")
        return prepared_data

    async def post_process(
        self, execution_result: Any, _context: SkillContext
    ) -> DummyOutput:
        if execution_result == 777 * 2:
            raise ValueError("Post process crash")
        return DummyOutput(doubled_value=execution_result)


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Ensure the global registry is clean before each test run."""
    registry.clear()


def test_skill_registration() -> None:
    """Test registering and retrieving skills from the registry."""
    skill = DummySkill()
    registry.register(skill)

    # Retrieval check
    resolved = registry.get("dummy", "1.0.0")
    assert resolved == skill

    # Case-insensitivity check
    assert registry.get("DUMMY", "1.0.0") == skill

    # Missing lookup failure
    with pytest.raises(SkillNotFoundError):
        registry.get("non_existent", "1.0.0")

    with pytest.raises(SkillNotFoundError):
        registry.get("dummy", "2.0.0")


@pytest.mark.asyncio
async def test_skill_execution_success() -> None:
    """Test executing a skill that runs perfectly through all lifecycle stages."""
    skill = DummySkill()
    context = SkillContext(request_id="req-1", correlation_id="corr-1")
    req = SkillRequest(input_data=DummyInput(value=10), context=context)

    result = await SkillExecutor.execute(skill, req)

    assert result.success is True
    assert result.data is not None
    assert result.data.doubled_value == 20
    assert result.error_message is None
    assert result.latency_ms > 0.0


@pytest.mark.asyncio
async def test_skill_validation_failure() -> None:
    """Test validation errors mapping from execution runs."""
    skill = DummySkill()
    context = SkillContext()
    # Negative value will fail validation
    req = SkillRequest(input_data=DummyInput(value=-5), context=context)

    result = await SkillExecutor.execute(skill, req)

    assert result.success is False
    assert result.data is None
    assert "Value cannot be negative" in result.error_message


@pytest.mark.asyncio
async def test_skill_stage_failures() -> None:
    """Test that runtime crashes in prepare, execute, and post_process map to SkillExecutionError."""
    skill = DummySkill()
    context = SkillContext()

    # Case A: Prepare stage crash (value 999)
    req_prep = SkillRequest(input_data=DummyInput(value=999), context=context)
    res_prep = await SkillExecutor.execute(skill, req_prep)
    assert res_prep.success is False
    assert "Skill preparation stage failed" in res_prep.error_message

    # Case B: Execute stage crash (value 888)
    req_exec = SkillRequest(input_data=DummyInput(value=888), context=context)
    res_exec = await SkillExecutor.execute(skill, req_exec)
    assert res_exec.success is False
    assert "Skill execution stage failed" in res_exec.error_message

    # Case C: Post-process stage crash (value 777)
    req_post = SkillRequest(input_data=DummyInput(value=777), context=context)
    res_post = await SkillExecutor.execute(skill, req_post)
    assert res_post.success is False
    assert "Skill post-processing stage failed" in res_post.error_message
