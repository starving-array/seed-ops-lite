"""Unit tests for the Schema Validation Agent, planner, and aggregator."""

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.schema_validation import (
    PlannerException,
    SchemaValidationAgent,
    SchemaValidationAggregator,
    SchemaValidationPlanner,
)
from app.llm.models import LLMResponse
from app.skills.context import SkillContext
from app.skills.registry import registry
from app.skills.schema_validation.registry import register_validation_skills
from app.telemetry.token_usage import TokenUsage


@pytest.fixture(autouse=True)
def setup_validation_skills() -> None:
    """Ensure the standard schema validation skills are registered before each test."""
    registry.clear()
    register_validation_skills()


def test_planner_resolves_skills() -> None:
    """Verify the planner correctly retrieves all core validation skills from the registry."""
    planner = SchemaValidationPlanner()
    plan = planner.plan()
    assert len(plan) == 5
    assert [s.name for s in plan] == [
        "structure",
        "relationships",
        "naming",
        "data_quality",
        "best_practices",
    ]


def test_planner_raises_on_unregistered_skill() -> None:
    """Verify the planner raises a PlannerException when resolving a missing skill."""
    planner = SchemaValidationPlanner(skill_names=["non_existent_skill"])
    with pytest.raises(PlannerException) as exc:
        planner.plan()
    assert "Failed to resolve validation skill" in str(exc.value)


@pytest.mark.asyncio
async def test_aggregator_logic() -> None:
    """Test findings deduplication, sorting by severity, recommendation extraction, and status mapping."""
    from app.skills.models import SkillResponse
    from app.skills.schema_validation.models import (
        Finding,
        NamingValidationResult,
        StructureValidationResult,
    )

    # 1. Structure skill response with duplicates & high severity
    struct_res = SkillResponse[StructureValidationResult](
        success=True,
        data=StructureValidationResult(
            is_valid=False,
            table_count=2,
            findings=[
                Finding(
                    severity="high",
                    description="Duplicate table name",
                    suggestion="Rename it",
                ),
                Finding(
                    severity="high",
                    description="Duplicate table name",  # exact duplicate to be removed
                    suggestion="Rename it",
                ),
                Finding(
                    severity="low",
                    description="Missing primary key on metadata table",
                    suggestion="Add PK",
                ),
            ],
            observations=["Found some tables"],
        ),
        latency_ms=10.0,
    )

    # 2. Naming skill response with medium severity
    naming_res = SkillResponse[NamingValidationResult](
        success=True,
        data=NamingValidationResult(
            is_valid=False,
            findings=[
                Finding(
                    severity="medium",
                    description="Column is not snake_case",
                    suggestion="Rename column to snake_case",
                )
            ],
            observations=[],
        ),
        latency_ms=15.0,
    )

    aggregator = SchemaValidationAggregator()
    # Mock executive summary LLM gateway call to return fallback summary
    with patch.object(
        aggregator, "_generate_executive_summary", return_value="Test summary text"
    ):
        report = await aggregator.aggregate(
            {"structure": struct_res, "naming": naming_res},
            total_duration_ms=45.0,
        )

        assert report.overall_status == "fail"  # due to 'high' finding
        assert len(report.findings) == 3  # deduplicated from 4
        assert report.findings[0].severity == "high"  # sorted high first
        assert report.findings[1].severity == "medium"
        assert report.findings[2].severity == "low"
        assert len(report.recommendations) == 3
        assert "Rename it" in report.recommendations
        assert "Rename column to snake_case" in report.recommendations
        assert report.execution_duration_ms == 45.0
        assert report.executed_skills == ["structure", "naming"]
        assert report.execution_statistics["structure"]["success"] is True


@pytest.mark.asyncio
async def test_agent_end_to_end_success() -> None:
    """Test full sequential execution of the agent, mocking all LLM responses."""
    usage = TokenUsage(
        provider="Google",
        model="gemini-2.5-flash",
        latency_ms=50.0,
    )

    # Mock responses for the five skills plus the summary aggregator LLM call
    mock_responses = [
        # StructureSkill
        LLMResponse(
            text='{"is_valid": true, "table_count": 1, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        # RelationshipsSkill
        LLMResponse(
            text='{"is_valid": true, "fk_count": 0, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        # NamingSkill
        LLMResponse(
            text='{"is_valid": true, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        # DataQualitySkill
        LLMResponse(
            text='{"is_valid": true, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        # BestPracticesSkill
        LLMResponse(
            text='{"is_valid": true, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        # Aggregator summary generation
        LLMResponse(
            text='{"summary": "The schema layout has passed all structure, relationship, naming, quality, and performance best practice rules."}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
    ]

    with patch(
        "app.llm.provider.GeminiProvider.generate", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.side_effect = mock_responses
        agent = SchemaValidationAgent()
        report = await agent.validate_schema(
            schema_ddl="CREATE TABLE users (id INT PRIMARY KEY);",
            context=SkillContext(request_id="req-agent-123"),
        )

        assert report.overall_status == "pass"
        assert (
            report.summary
            == "Database schema validation completed successfully with no findings detected."
        )
        assert len(report.findings) == 0
        assert len(report.warnings) == 0
        assert report.executed_skills == [
            "structure",
            "relationships",
            "naming",
            "data_quality",
            "best_practices",
        ]
        assert report.execution_statistics["structure"]["success"] is True
        assert report.execution_duration_ms > 0.0


@pytest.mark.asyncio
async def test_agent_with_failed_skill_reports_warning() -> None:
    """Verify that if one skill fails, the agent continues and reports a warning in the output."""
    usage = TokenUsage(
        provider="Google",
        model="gemini-2.5-flash",
        latency_ms=50.0,
    )

    # 1. StructureSkill generates success
    # 2. RelationshipsSkill generates invalid JSON (causes a parsing crash)
    # 3. NamingSkill generates success
    # 4. DataQualitySkill generates success
    # 5. BestPracticesSkill generates success
    # 6. Aggregator summary LLM call
    mock_responses = [
        LLMResponse(
            text='{"is_valid": true, "table_count": 1, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        LLMResponse(
            text="bad-json-forcing-failure",
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        LLMResponse(
            text='{"is_valid": true, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        LLMResponse(
            text='{"is_valid": true, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        LLMResponse(
            text='{"is_valid": true, "observations": [], "findings": []}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
        LLMResponse(
            text='{"summary": "Summary with a failed skill."}',
            usage=usage,
            raw_response={"candidates": [{"finishReason": "STOP"}]},
        ),
    ]

    with patch(
        "app.llm.provider.GeminiProvider.generate", new_callable=AsyncMock
    ) as mock_generate:
        mock_generate.side_effect = mock_responses
        agent = SchemaValidationAgent()
        report = await agent.validate_schema(
            schema_ddl="CREATE TABLE users (id INT PRIMARY KEY);",
            context=SkillContext(),
        )

        # Agent should still run successfully and report details
        assert report.overall_status == "pass"  # findings list is empty
        assert len(report.warnings) == 1
        assert "relationships" in report.warnings[0]
        assert report.execution_statistics["relationships"]["success"] is False
