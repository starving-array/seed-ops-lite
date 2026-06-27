"""Integration tests for the schema assistant endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.agents.schema_validation.models import AgentFinding, SchemaValidationReport


@pytest.mark.asyncio
async def test_ai_assist_empty_tables(client: AsyncClient) -> None:
    """Test the /schema/ai-assist endpoint with no tables."""
    payload = {"tables": [], "relationships": []}
    response = await client.post("/schema/ai-assist", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Completed"
    assert "No tables configured" in data["summary"]
    assert len(data["suggestions"]) == 0


@pytest.mark.asyncio
async def test_ai_assist_success(client: AsyncClient) -> None:
    """Test the /schema/ai-assist endpoint when execution succeeds."""
    mock_report = SchemaValidationReport(
        overall_status="warning",
        summary="Database schema has some opportunities for improvement.",
        findings=[
            AgentFinding(
                category="naming",
                severity="low",
                description="Table name: USERS should be lowercase snake_case.",
                suggestion="Rename table to users.",
            ),
            AgentFinding(
                category="relationships",
                severity="medium",
                description="Missing foreign key: order table should reference users table.",
                suggestion="Add user_id column and foreign key reference.",
            ),
            AgentFinding(
                category="best_practices",
                severity="medium",
                description="Performance: Missing index on user_id column.",
                suggestion="Create index on user_id.",
            ),
        ],
        recommendations=["Rename table to users.", "Add user_id column and foreign key reference.", "Create index on user_id."],
        warnings=[],
        execution_statistics={},
        executed_skills=["naming", "relationships", "best_practices"],
        execution_duration_ms=120.0,
    )

    payload = {
        "tables": [
            {
                "id": "1",
                "name": "USERS",
                "columns": [
                    {
                        "id": "c1",
                        "name": "id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                        "defaultValue": "",
                    }
                ],
            }
        ],
        "relationships": [],
    }

    with patch(
        "app.agents.schema_validation.agent.SchemaValidationAgent.validate_schema",
        new_callable=AsyncMock,
        return_value=mock_report,
    ):
        response = await client.post("/schema/ai-assist", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Completed"
        assert data["summary"] == "Database schema has some opportunities for improvement."
        assert len(data["suggestions"]) == 3

        suggestions = data["suggestions"]

        # Verify first suggestion
        assert suggestions[0]["category"] == "Naming"
        assert suggestions[0]["severity"] == "low"
        assert suggestions[0]["title"] == "Table name"
        assert "USERS should be lowercase" in suggestions[0]["explanation"]
        assert suggestions[0]["suggestedAction"] == "Rename table to users."

        # Verify performance suggestion gets correctly classified as Performance
        perf_sug = next(s for s in suggestions if s["title"] == "Performance")
        assert perf_sug["category"] == "Performance"
        assert perf_sug["severity"] == "medium"
        assert perf_sug["suggestedAction"] == "Create index on user_id."


@pytest.mark.asyncio
async def test_ai_assist_failure(client: AsyncClient) -> None:
    """Test the /schema/ai-assist endpoint when the agent raises an exception."""
    payload = {
        "tables": [
            {
                "id": "1",
                "name": "users",
                "columns": [
                    {
                        "id": "c1",
                        "name": "id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                        "defaultValue": "",
                    }
                ],
            }
        ],
        "relationships": [],
    }

    with patch(
        "app.agents.schema_validation.agent.SchemaValidationAgent.validate_schema",
        new_callable=AsyncMock,
        side_effect=Exception("Gemini API key is not configured."),
    ):
        response = await client.post("/schema/ai-assist", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Failed"
        assert "AI Schema Assistant is currently unavailable" in data["summary"]
        assert len(data["suggestions"]) == 0
