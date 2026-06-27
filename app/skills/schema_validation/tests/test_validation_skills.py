"""Unit tests for the schema validation skills verifying registration and execution logic."""

from unittest.mock import AsyncMock, patch

import pytest

import app.skills.schema_validation  # noqa: F401
from app.llm.gateway import LLMGateway
from app.llm.models import LLMResponse
from app.skills.context import SkillContext
from app.skills.executor import SkillExecutor
from app.skills.models import SkillRequest
from app.skills.registry import registry
from app.skills.schema_validation.best_practices import BestPracticesSkill
from app.skills.schema_validation.data_quality import DataQualitySkill
from app.skills.schema_validation.models import SchemaValidationInput
from app.skills.schema_validation.naming import NamingSkill
from app.skills.schema_validation.relationships import RelationshipsSkill
from app.skills.schema_validation.structure import StructureSkill
from app.telemetry.token_usage import TokenUsage


def test_skills_are_registered() -> None:
    """Verify all 5 schema validation skills are registered in the global registry."""
    from app.skills.schema_validation.registry import register_validation_skills

    register_validation_skills()
    assert registry.get("structure", "1.0.0") is not None
    assert registry.get("relationships", "1.0.0") is not None
    assert registry.get("naming", "1.0.0") is not None
    assert registry.get("data_quality", "1.0.0") is not None
    assert registry.get("best_practices", "1.0.0") is not None


@pytest.mark.asyncio
async def test_validation_skills_empty_input_fails() -> None:
    """Verify that all skills fail validation on empty input."""
    context = SkillContext()
    empty_req = SkillRequest(
        input_data=SchemaValidationInput(schema_ddl="   "), context=context
    )

    skills = [
        StructureSkill(),
        RelationshipsSkill(),
        NamingSkill(),
        DataQualitySkill(),
        BestPracticesSkill(),
    ]

    for skill in skills:
        res = await SkillExecutor.execute(skill, empty_req)
        assert res.success is False
        assert "Schema DDL cannot be empty" in res.error_message


@pytest.mark.asyncio
async def test_structure_skill_success() -> None:
    """Test successful run of the Structure Validation Skill."""
    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(
        provider="Google",
        model="gemini-1.5-pro",
        latency_ms=100.0,
        prompt_tokens=5,
        completion_tokens=5,
        total_tokens=10,
        estimated_cost=0.0001,
    )
    mock_response = LLMResponse(
        text='{"is_valid": true, "table_count": 2, "observations": ["All good"], "findings": []}',
        usage=usage,
        raw_response={"candidates": [{"finishReason": "STOP"}]},
        request_id="req-1",
        correlation_id="corr-1",
    )
    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        skill = StructureSkill(gateway=gateway)
        context = SkillContext()
        req = SkillRequest(
            input_data=SchemaValidationInput(
                schema_ddl="CREATE TABLE t1 (id INT PRIMARY KEY);"
            ),
            context=context,
        )

        res = await SkillExecutor.execute(skill, req)

        assert res.success is True
        assert res.data is not None
        assert res.data.is_valid is True
        assert res.data.table_count == 2
        assert "All good" in res.data.observations


@pytest.mark.asyncio
async def test_relationships_skill_success() -> None:
    """Test successful run of the Relationships Validation Skill."""
    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(provider="Google", model="gemini-1.5-pro", latency_ms=100.0)
    mock_response = LLMResponse(
        text='{"is_valid": false, "fk_count": 1, "observations": [], "findings": [{"severity": "high", "description": "loop detected", "suggestion": "break loop"}]}',
        usage=usage,
        raw_response={"candidates": [{"finishReason": "STOP"}]},
    )
    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        skill = RelationshipsSkill(gateway=gateway)
        req = SkillRequest(
            input_data=SchemaValidationInput(schema_ddl="CREATE TABLE t1;"),
            context=SkillContext(),
        )

        res = await SkillExecutor.execute(skill, req)

        assert res.success is True
        assert res.data is not None
        assert res.data.is_valid is False
        assert res.data.fk_count == 1
        assert len(res.data.findings) == 1
        assert res.data.findings[0].severity == "high"
        assert res.data.findings[0].description == "loop detected"


@pytest.mark.asyncio
async def test_naming_skill_success() -> None:
    """Test successful run of the Naming Validation Skill."""
    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(provider="Google", model="gemini-1.5-pro", latency_ms=100.0)
    mock_response = LLMResponse(
        text='{"is_valid": true, "observations": ["No violations"], "findings": []}',
        usage=usage,
        raw_response={"candidates": [{"finishReason": "STOP"}]},
    )
    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        skill = NamingSkill(gateway=gateway)
        req = SkillRequest(
            input_data=SchemaValidationInput(schema_ddl="CREATE TABLE t1;"),
            context=SkillContext(),
        )

        res = await SkillExecutor.execute(skill, req)

        assert res.success is True
        assert res.data is not None
        assert res.data.is_valid is True
        assert "No violations" in res.data.observations


@pytest.mark.asyncio
async def test_data_quality_skill_success() -> None:
    """Test successful run of the Data Quality Validation Skill."""
    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(provider="Google", model="gemini-1.5-pro", latency_ms=100.0)
    mock_response = LLMResponse(
        text='{"is_valid": true, "observations": [], "findings": []}',
        usage=usage,
        raw_response={"candidates": [{"finishReason": "STOP"}]},
    )
    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        skill = DataQualitySkill(gateway=gateway)
        req = SkillRequest(
            input_data=SchemaValidationInput(schema_ddl="CREATE TABLE t1;"),
            context=SkillContext(),
        )

        res = await SkillExecutor.execute(skill, req)

        assert res.success is True
        assert res.data is not None
        assert res.data.is_valid is True


@pytest.mark.asyncio
async def test_best_practices_skill_success() -> None:
    """Test successful run of the Best Practices Validation Skill."""
    gateway = LLMGateway()
    mock_provider = AsyncMock()

    usage = TokenUsage(provider="Google", model="gemini-1.5-pro", latency_ms=100.0)
    mock_response = LLMResponse(
        text='{"is_valid": true, "observations": ["Good layout"], "findings": []}',
        usage=usage,
        raw_response={"candidates": [{"finishReason": "STOP"}]},
    )
    mock_provider.generate.return_value = mock_response

    with patch.object(gateway, "_provider", mock_provider):
        skill = BestPracticesSkill(gateway=gateway)
        req = SkillRequest(
            input_data=SchemaValidationInput(schema_ddl="CREATE TABLE t1;"),
            context=SkillContext(),
        )

        res = await SkillExecutor.execute(skill, req)

        assert res.success is True
        assert res.data is not None
        assert res.data.is_valid is True
        assert "Good layout" in res.data.observations
