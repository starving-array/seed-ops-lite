import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def override_redis(app: FastAPI) -> Any:
    """Mock Redis backend operations using an in-memory dictionary."""
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
async def test_e2e_complete_workflow(client: AsyncClient) -> None:
    """End-to-End verification of the complete SafeSeed-Ops workflow.

    Pipeline:
    1. Schema Validation Pre-check
    2. AI Schema Assistant Suggestions
    3. Start Data Generation Job
    4. Data Generation Progress Monitoring
    5. List Exportable Datasets
    6. Trigger Export Job
    7. Export Progress Monitoring
    8. Download Final File
    """
    # Sample Schema State conforming to Pydantic models
    schema_state = {
        "tables": [
            {
                "id": "t-1",
                "name": "users",
                "columns": [
                    {
                        "id": "c-1",
                        "name": "id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                        "defaultValue": "",
                    },
                    {
                        "id": "c-2",
                        "name": "email",
                        "type": "VARCHAR",
                        "isPrimaryKey": False,
                        "isNullable": False,
                        "defaultValue": "",
                    },
                ],
            },
            {
                "id": "t-2",
                "name": "orders",
                "columns": [
                    {
                        "id": "c-3",
                        "name": "id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                        "defaultValue": "",
                    },
                    {
                        "id": "c-4",
                        "name": "user_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                        "defaultValue": "",
                    },
                ],
            },
        ],
        "relationships": [
            {
                "id": "r-1",
                "name": "fk_orders_users",
                "sourceTableId": "t-2",
                "sourceColumnId": "c-4",
                "targetTableId": "t-1",
                "targetColumnId": "c-1",
                "type": "many-to-one",
                "isRequired": True,
                "cascadeDelete": False,
                "cascadeUpdate": False,
            }
        ],
    }

    # Prepare Mock Report for AI Assistant
    from app.agents.schema_validation.models import AgentFinding, SchemaValidationReport
    mock_report = SchemaValidationReport(
        overall_status="warning",
        summary="Database schema has some opportunities for improvement.",
        findings=[
            AgentFinding(
                category="naming",
                severity="low",
                description="Table name users should be lowercase snake_case.",
                suggestion="Rename table to users.",
            )
        ],
        recommendations=["Rename table to users."],
        warnings=[],
        execution_statistics={},
        executed_skills=["naming"],
        execution_duration_ms=120.0,
    )

    # Prepare Mock AI Strategy Generator records
    async def mock_execute_contract(_gateway: Any, contract_request: Any) -> Any:
        import typing
        schema_cls = contract_request.response_schema
        record_type = schema_cls.model_fields["records"].annotation
        args = typing.get_args(record_type)
        dynamic_record_cls = args[0] if args else None

        dummy_records = []
        count = 5
        for i in range(count):
            field_values = {}
            if dynamic_record_cls:
                for f_name, f_field in dynamic_record_cls.model_fields.items():
                    f_annotation = f_field.annotation
                    if f_name == "id" or f_annotation is int:
                        field_values[f_name] = i + 1
                    elif f_annotation is float:
                        field_values[f_name] = float(i + 1)
                    elif f_annotation is bool:
                        field_values[f_name] = True
                    elif f_name == "email":
                        field_values[f_name] = f"user{i+1}@example.com"
                    else:
                        field_values[f_name] = f"mock_{f_name}_{i+1}"
                dummy_record = dynamic_record_cls(**field_values)
                dummy_records.append(dummy_record)

        response_data = schema_cls(records=dummy_records)

        from app.llm.contracts.response import AIContractResponse, ContractMetadata
        metadata = ContractMetadata(
            provider="MockProvider",
            model="MockModel",
            prompt_tokens=15,
            completion_tokens=25,
            total_tokens=40,
            estimated_cost=0.002,
            latency_ms=120.0,
        )

        return AIContractResponse(
            success=True,
            data=response_data,
            metadata=metadata,
            error=None,
        )

    # Patch the SchemaValidationAgent and the AI Seeder execution flow
    with patch(
        "app.agents.schema_validation.agent.SchemaValidationAgent.validate_schema",
        new_callable=AsyncMock,
        return_value=mock_report,
    ), patch(
        "app.seeder.ai.AIContractNormalizer.execute_contract",
        new_callable=AsyncMock,
        side_effect=mock_execute_contract,
    ):
        # 1. Schema Validation Pre-check
        validate_resp = await client.post("/schema/validate", json=schema_state)
        assert validate_resp.status_code == 200
        validation_data = validate_resp.json()
        assert isinstance(validation_data, list)

        # 2. AI Schema Assistant Suggestions
        ai_resp = await client.post("/schema/ai-assist", json=schema_state)
        assert ai_resp.status_code == 200
        ai_data = ai_resp.json()
        assert "status" in ai_data
        assert "suggestions" in ai_data

        # 3. Start Data Generation Job
        generate_payload = {
            "schemaState": schema_state,
            "rowTargets": {"users": 5, "orders": 5},
            "seed": 42,
            "batchSize": 5,
            "outputFormat": "json",
        }
        start_gen_resp = await client.post("/schema/generate", json=generate_payload)
        assert start_gen_resp.status_code == 200
        gen_data = start_gen_resp.json()
        assert "workflowId" in gen_data
        workflow_id = gen_data["workflowId"]

        # 4. Data Generation Progress Monitoring
        max_retries = 30
        for _ in range(max_retries):
            job_resp = await client.get(f"/schema/jobs/{workflow_id}")
            assert job_resp.status_code == 200
            job_data = job_resp.json()
            if job_data["status"] == "Completed":
                break
            if job_data["status"] == "Failed":
                pytest.fail(f"Generation job failed: {job_data.get('errorMessage')}")
            await asyncio.sleep(0.01)
        else:
            pytest.fail("Generation job timed out before completing.")

        # 5. List Exportable Datasets
        datasets_resp = await client.get("/schema/export/datasets")
        assert datasets_resp.status_code == 200
        datasets = datasets_resp.json()
        assert any(d["workflowId"] == workflow_id for d in datasets)

        # 6. Trigger Export Job
        export_payload = {
            "workflowId": workflow_id,
            "format": "csv",
            "tables": ["users", "orders"],
            "singleFile": False,
            "compression": True,
            "includeMetadata": True,
            "fileNameConvention": "timestamp",
        }
        start_export_resp = await client.post("/schema/export", json=export_payload)
        assert start_export_resp.status_code == 200
        export_job_data = start_export_resp.json()
        assert "jobId" in export_job_data
        export_job_id = export_job_data["jobId"]

        # 7. Export Progress Monitoring
        for _ in range(max_retries):
            export_status_resp = await client.get(f"/schema/jobs/{export_job_id}")
            assert export_status_resp.status_code == 200
            export_status_data = export_status_resp.json()
            if export_status_data["status"] == "Completed":
                break
            if export_status_data["status"] == "Failed":
                pytest.fail(f"Export job failed: {export_status_data.get('errorMessage')}")
            await asyncio.sleep(0.01)
        else:
            pytest.fail("Export job timed out before completing.")

        # 8. Download Final File
        download_resp = await client.get(f"/schema/export/{export_job_id}/download")
        assert download_resp.status_code == 200
        assert "Content-Disposition" in download_resp.headers
        assert "attachment" in download_resp.headers["Content-Disposition"]
        assert "Content-Length" in download_resp.headers
        assert int(download_resp.headers["Content-Length"]) > 0


@pytest.mark.asyncio
async def test_e2e_export_missing_records(client: AsyncClient) -> None:
    """Verify error handling when exporting a dataset that doesn't exist."""
    export_payload = {
        "workflowId": "missing-workflow-id",
        "format": "json",
        "tables": [],
        "singleFile": True,
        "compression": False,
        "includeMetadata": False,
        "fileNameConvention": "default",
    }

    start_export_resp = await client.post("/schema/export", json=export_payload)
    assert start_export_resp.status_code == 200
    export_job_id = start_export_resp.json()["jobId"]

    # Monitor the export job and verify it transitions to Failed
    max_retries = 30
    for _ in range(max_retries):
        export_status_resp = await client.get(f"/schema/jobs/{export_job_id}")
        export_status_data = export_status_resp.json()
        if export_status_data["status"] == "Failed":
            assert "no generated dataset records found" in export_status_data["errorMessage"].lower()
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Export job did not transition to Failed for missing records.")
