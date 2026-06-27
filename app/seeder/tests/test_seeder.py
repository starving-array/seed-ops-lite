"""Tests for the Hybrid Seeder capability."""

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, Field

from app.llm.contracts.response import AIContractResponse, ContractMetadata
from app.seeder.exceptions import StrategySelectionException, ValidationException
from app.seeder.models import FieldDefinition, GenerationStrategy, SeedRequest
from app.seeder.seeder import HybridSeeder
from app.seeder.strategy import StrategyRegistry
from app.workers.models import ExecutionUnit


def test_strategy_selection() -> None:
    """Test that strategies are correctly selected based on field types."""
    seeder = HybridSeeder()

    # Hybrid
    fields = {
        "id": FieldDefinition(type="id"),
        "name": FieldDefinition(type="name"),
        "created_at": FieldDefinition(type="date"),
    }
    overall, det, ai = seeder.select_strategy(fields)
    assert overall == GenerationStrategy.HYBRID
    assert "id" in det
    assert "created_at" in det
    assert "name" in ai

    # Deterministic only
    fields_det = {
        "id": FieldDefinition(type="id"),
        "uid": FieldDefinition(type="uuid"),
    }
    overall_det, _, _ = seeder.select_strategy(fields_det)
    assert overall_det == GenerationStrategy.DETERMINISTIC

    # AI only
    fields_ai = {
        "address": FieldDefinition(type="address"),
        "biography": FieldDefinition(type="biography"),
    }
    overall_ai, _, _ = seeder.select_strategy(fields_ai)
    assert overall_ai == GenerationStrategy.AI

    # Error case
    with pytest.raises(StrategySelectionException):
        seeder.select_strategy({"unknown": FieldDefinition(type="invalid_type")})


def test_strategy_registry_extensibility() -> None:
    """Test that strategy registry can be extended dynamically."""
    custom_registry = StrategyRegistry()
    custom_registry.register("phone", GenerationStrategy.DETERMINISTIC)
    custom_registry.register("resume", GenerationStrategy.AI)

    seeder = HybridSeeder(registry=custom_registry)
    fields = {
        "phone": FieldDefinition(type="phone"),
        "resume": FieldDefinition(type="resume"),
    }

    overall, det, ai = seeder.select_strategy(fields)
    assert overall == GenerationStrategy.HYBRID
    assert "phone" in det
    assert "resume" in ai


@pytest.mark.asyncio
async def test_reproducibility() -> None:
    """Test that same seed yields identical results, and different seed/unseeded yields distinct results."""
    seeder = HybridSeeder()
    fields = {
        "score": FieldDefinition(
            type="numeric_range", rules={"min": 0, "max": 1000, "subtype": "int"}
        ),
        "status": FieldDefinition(
            type="enum", rules={"values": ["a", "b", "c", "d", "e"]}
        ),
        "uid": FieldDefinition(type="uuid"),
        "flag": FieldDefinition(type="boolean"),
    }

    # Run with seed 42
    request1 = SeedRequest(target="repro_table", num_records=10, fields=fields, seed=42)
    result1 = await seeder.seed(request1)

    # Run with seed 42 again
    request2 = SeedRequest(target="repro_table", num_records=10, fields=fields, seed=42)
    result2 = await seeder.seed(request2)

    # Run with seed 100
    request3 = SeedRequest(
        target="repro_table", num_records=10, fields=fields, seed=100
    )
    result3 = await seeder.seed(request3)

    # Assert request1 results match request2 exactly
    for i in range(10):
        assert result1.records[i].data == result2.records[i].data

    # Assert request3 results differ from request1 due to different seed
    diff_found = False
    for i in range(10):
        if result1.records[i].data != result3.records[i].data:
            diff_found = True
            break
    assert diff_found, "Seed 42 and Seed 100 generated identical outputs"


@pytest.mark.asyncio
async def test_deterministic_generation() -> None:
    """Test deterministic generation rules and boundaries."""
    seeder = HybridSeeder()
    request = SeedRequest(
        target="users",
        num_records=5,
        fields={
            "id": FieldDefinition(type="id", rules={"start": 10, "step": 2}),
            "uid": FieldDefinition(type="uuid"),
            "status": FieldDefinition(type="enum", rules={"values": ["ok", "pending"]}),
            "score": FieldDefinition(
                type="numeric_range",
                rules={"min": 50, "max": 100, "subtype": "int"},
            ),
            "active": FieldDefinition(type="boolean", rules={"true_probability": 1.0}),
            "custom": FieldDefinition(
                type="rule_based", rules={"prefix": "USER_", "sequential": True}
            ),
        },
    )

    result = await seeder.seed(request)
    assert result.success
    assert len(result.records) == 5
    assert result.statistics.total_records == 5
    assert result.statistics.successful_records == 5
    assert result.statistics.failed_records == 0
    assert result.statistics.deterministic_fields_count == 30
    assert result.statistics.ai_fields_count == 0

    for i, record in enumerate(result.records):
        data = record.data
        assert record.validation_passed
        assert data["id"] == 10 + i * 2
        assert len(data["uid"]) == 36
        assert data["status"] in ["ok", "pending"]
        assert 50 <= data["score"] <= 100
        assert data["active"] is True
        assert data["custom"] == f"USER_{1 + i}"


@pytest.mark.asyncio
async def test_ai_generation() -> None:
    """Test AI-assisted generation using mocks for AI Contract Layer execution."""
    seeder = HybridSeeder()
    request = SeedRequest(
        target="profiles",
        num_records=2,
        fields={
            "bio": FieldDefinition(type="biography"),
            "address": FieldDefinition(type="address"),
        },
    )

    class MockRecord(BaseModel):
        bio: str
        address: str

    class MockResponse(BaseModel):
        records: list[MockRecord] = Field(...)

    mock_response_data = MockResponse(
        records=[
            MockRecord(bio="Bio 1", address="Address 1"),
            MockRecord(bio="Bio 2", address="Address 2"),
        ]
    )

    mock_metadata = ContractMetadata(
        provider="MockProvider",
        model="MockModel",
        prompt_tokens=15,
        completion_tokens=25,
        total_tokens=40,
        estimated_cost=0.002,
        latency_ms=120.0,
    )

    mock_contract_response = AIContractResponse(
        success=True,
        data=mock_response_data,
        metadata=mock_metadata,
        error=None,
    )

    with patch(
        "app.seeder.ai.AIContractNormalizer.execute_contract",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = mock_contract_response

        result = await seeder.seed(request)
        assert result.success
        assert len(result.records) == 2
        assert result.statistics.total_records == 2
        assert result.statistics.successful_records == 2
        assert result.statistics.failed_records == 0
        assert result.statistics.deterministic_fields_count == 0
        assert result.statistics.ai_fields_count == 4

        # Verify measured LLM metrics
        assert result.statistics.prompt_tokens == 15
        assert result.statistics.completion_tokens == 25
        assert result.statistics.total_tokens == 40
        assert result.statistics.estimated_cost == 0.002
        assert result.statistics.latency_ms == 120.0

        assert result.records[0].data["bio"] == "Bio 1"
        assert result.records[0].data["address"] == "Address 1"
        assert result.records[1].data["bio"] == "Bio 2"
        assert result.records[1].data["address"] == "Address 2"


@pytest.mark.asyncio
async def test_hybrid_generation() -> None:
    """Test merging deterministic and AI-generated fields in hybrid mode."""
    seeder = HybridSeeder()
    request = SeedRequest(
        target="hybrid_target",
        num_records=2,
        fields={
            "id": FieldDefinition(type="id"),
            "bio": FieldDefinition(type="biography"),
        },
    )

    class MockRecord(BaseModel):
        bio: str

    class MockResponse(BaseModel):
        records: list[MockRecord] = Field(...)

    mock_response_data = MockResponse(
        records=[
            MockRecord(bio="Bio 1"),
            MockRecord(bio="Bio 2"),
        ]
    )

    mock_metadata = ContractMetadata(
        provider="MockProvider",
        model="MockModel",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        estimated_cost=0.001,
        latency_ms=100.0,
    )

    mock_contract_response = AIContractResponse(
        success=True,
        data=mock_response_data,
        metadata=mock_metadata,
        error=None,
    )

    with patch(
        "app.seeder.ai.AIContractNormalizer.execute_contract",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = mock_contract_response

        result = await seeder.seed(request)
        assert result.success
        assert len(result.records) == 2
        assert result.records[0].data["id"] == 1
        assert result.records[0].data["bio"] == "Bio 1"
        assert result.records[1].data["id"] == 2
        assert result.records[1].data["bio"] == "Bio 2"
        assert result.statistics.deterministic_fields_count == 2
        assert result.statistics.ai_fields_count == 2


@pytest.mark.asyncio
async def test_validation_failure() -> None:
    """Test validation failure behavior when generated values don't respect rules."""
    seeder = HybridSeeder()
    request = SeedRequest(
        target="profiles",
        num_records=1,
        fields={
            "name": FieldDefinition(type="name", rules={"min_length": 10}),
        },
    )

    class MockRecord(BaseModel):
        name: str

    class MockResponse(BaseModel):
        records: list[MockRecord] = Field(...)

    # Returning a name shorter than the rule's min_length of 10
    mock_response_data = MockResponse(records=[MockRecord(name="Short")])
    mock_contract_response = AIContractResponse(
        success=True,
        data=mock_response_data,
        metadata=ContractMetadata(
            provider="Mock",
            model="Mock",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            estimated_cost=0,
            latency_ms=0,
        ),
        error=None,
    )

    with patch(
        "app.seeder.ai.AIContractNormalizer.execute_contract",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = mock_contract_response

        result = await seeder.seed(request)
        assert not result.success
        assert len(result.records) == 1
        assert not result.records[0].validation_passed
        assert "length 5 is less than min_length 10" in result.records[0].errors[0]
        assert result.statistics.failed_records == 1
        assert result.statistics.successful_records == 0


@pytest.mark.asyncio
async def test_configurable_strict_validation() -> None:
    """Test that strict validation raises a ValidationException when records fail verification."""
    seeder = HybridSeeder()
    request = SeedRequest(
        target="profiles",
        num_records=1,
        fields={
            "name": FieldDefinition(type="name", rules={"min_length": 10}),
        },
        strict=True,
    )

    class MockRecord(BaseModel):
        name: str

    class MockResponse(BaseModel):
        records: list[MockRecord] = Field(...)

    mock_response_data = MockResponse(records=[MockRecord(name="Short")])
    mock_contract_response = AIContractResponse(
        success=True,
        data=mock_response_data,
        metadata=ContractMetadata(
            provider="Mock",
            model="Mock",
            prompt_tokens=1,
            completion_tokens=1,
            total_tokens=2,
            estimated_cost=0,
            latency_ms=0,
        ),
        error=None,
    )

    with patch(
        "app.seeder.ai.AIContractNormalizer.execute_contract",
        new_callable=AsyncMock,
    ) as mock_exec:
        mock_exec.return_value = mock_contract_response

        with pytest.raises(ValidationException) as excinfo:
            await seeder.seed(request)
        assert "validation failed in strict mode" in str(excinfo.value)


@pytest.mark.asyncio
async def test_worker_framework_integration() -> None:
    """Test mapping an ExecutionUnit to SeedRequest and returning serialized result."""
    seeder = HybridSeeder()
    unit = ExecutionUnit(
        unit_id="unit-123",
        task_type="seeder",
        target="users_table",
        payload={
            "num_records": 3,
            "fields": {
                "id": {"type": "id", "rules": {"start": 100}},
                "uid": {"type": "uuid"},
            },
        },
    )

    result_dict = await seeder.execute_unit(unit)
    assert result_dict["target"] == "users_table"
    assert len(result_dict["records"]) == 3
    assert result_dict["success"] is True
    assert result_dict["records"][0]["data"]["id"] == 100
