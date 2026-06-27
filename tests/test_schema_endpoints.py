"""Integration tests for the schema assistant endpoints."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.agents.schema_validation.models import AgentFinding, SchemaValidationReport


@pytest.fixture(autouse=True)
def override_redis(app: FastAPI) -> Any:
    store = {}
    mock_redis = AsyncMock()

    async def mock_get(key: str) -> bytes | None:
        return store.get(key)

    async def mock_set(
        key: str, value: Any, *_args: Any, **_kwargs: Any
    ) -> bool:
        store[key] = (
            value if isinstance(value, bytes) else str(value).encode("utf-8")
        )
        return True

    async def mock_sadd(key: str, member: str) -> int:
        if key not in store:
            store[key] = set()
        store[key].add(member)
        return 1

    async def mock_smembers(key: str) -> set[bytes]:
        val = store.get(key, set())
        return {
            m.encode("utf-8") if isinstance(m, str) else m for m in val
        }

    mock_redis.get = mock_get
    mock_redis.set = mock_set
    mock_redis.sadd = mock_sadd
    mock_redis.smembers = mock_smembers

    from app.api.deps import get_redis

    app.dependency_overrides[get_redis] = lambda: mock_redis
    yield
    app.dependency_overrides.pop(get_redis, None)


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


@pytest.mark.asyncio
async def test_start_generation(client: AsyncClient) -> None:
    """Test start synthetic data generation endpoint."""
    payload = {
        "schemaState": {
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
        },
        "rowTargets": {"users": 10},
        "seed": 42,
        "batchSize": 5,
        "outputFormat": "json",
    }
    response = await client.post("/schema/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "workflowId" in data
    assert data["status"] == "Queued"
    assert len(data["progress"]) == 1
    assert data["progress"][0]["tableName"] == "users"
    assert data["progress"][0]["targetRows"] == 10


@pytest.mark.asyncio
async def test_get_generation_status_not_found(client: AsyncClient) -> None:
    """Test get status for a missing workflow session."""
    response = await client.get("/schema/generate/missing-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancel_generation_success(client: AsyncClient) -> None:
    """Test cancellation of generation workflow."""
    # First, mock starting to populate a status in Redis
    payload = {
        "schemaState": {"tables": [], "relationships": []},
        "rowTargets": {},
    }
    # We can just start it (even with empty tables, it saves a workflow ID)
    start_resp = await client.post("/schema/generate", json=payload)
    assert start_resp.status_code == 200
    workflow_id = start_resp.json()["workflowId"]

    # Cancel it
    cancel_resp = await client.post(f"/schema/generate/{workflow_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "success"


@pytest.mark.asyncio
async def test_download_generated_data(client: AsyncClient) -> None:
    """Test download endpoint returns generated metadata."""
    payload = {
        "schemaState": {"tables": [], "relationships": []},
        "rowTargets": {},
    }
    start_resp = await client.post("/schema/generate", json=payload)
    workflow_id = start_resp.json()["workflowId"]

    download_resp = await client.get(f"/schema/generate/{workflow_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.json()["status"] == "success"
    assert download_resp.json()["workflowId"] == workflow_id


@pytest.mark.asyncio
async def test_list_jobs(client: AsyncClient) -> None:
    """Test retrieving historical and active background jobs."""
    # Create a job first by starting generation
    payload = {
        "schemaState": {"tables": [], "relationships": []},
        "rowTargets": {},
    }
    start_resp = await client.post("/schema/generate", json=payload)
    assert start_resp.status_code == 200
    workflow_id = start_resp.json()["workflowId"]

    # Get job history list
    list_resp = await client.get("/schema/jobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert len(jobs) >= 1

    # Verify the created job exists in history
    our_job = next(j for j in jobs if j["jobId"] == workflow_id)
    assert our_job["status"] in ("Queued", "Completed")
    assert our_job["type"] == "generation"

    # Test filtering by status
    curr_status = our_job["status"]
    filter_resp = await client.get(f"/schema/jobs?status={curr_status}")
    assert filter_resp.status_code == 200
    assert any(j["jobId"] == workflow_id for j in filter_resp.json())

    other_status = "Failed" if curr_status != "Failed" else "Queued"
    filter_none_resp = await client.get(f"/schema/jobs?status={other_status}")
    assert filter_none_resp.status_code == 200
    assert not any(j["jobId"] == workflow_id for j in filter_none_resp.json())


@pytest.mark.asyncio
async def test_get_job_details(client: AsyncClient) -> None:
    """Test retrieving job details by ID."""
    payload = {
        "schemaState": {"tables": [], "relationships": []},
        "rowTargets": {},
    }
    start_resp = await client.post("/schema/generate", json=payload)
    workflow_id = start_resp.json()["workflowId"]

    detail_resp = await client.get(f"/schema/jobs/{workflow_id}")
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["jobId"] == workflow_id
    assert data["status"] in ("Queued", "Completed")
    assert data["type"] == "generation"


@pytest.mark.asyncio
async def test_cancel_job_from_history(client: AsyncClient) -> None:
    """Test cancelling a job directly from job history."""
    payload = {
        "schemaState": {"tables": [], "relationships": []},
        "rowTargets": {},
    }
    start_resp = await client.post("/schema/generate", json=payload)
    workflow_id = start_resp.json()["workflowId"]

    cancel_resp = await client.post(f"/schema/jobs/{workflow_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "success"

    # Verify job status transitioned to Cancelled
    detail_resp = await client.get(f"/schema/jobs/{workflow_id}")
    assert detail_resp.json()["status"] == "Cancelled"


