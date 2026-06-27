"""Tests for the SeedOps CLI Application."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.cli.cli import CLIApplication
from app.cli.models import ExitStatus


@pytest.fixture(autouse=True)
def mock_ai_contract_execution():
    """Autouse fixture to mock AIContractNormalizer.execute_contract for all CLI tests."""
    import typing
    from unittest.mock import patch

    from app.llm.contracts.response import AIContractResponse, ContractMetadata

    async def mock_execute(_gateway, contract_request):
        schema_cls = contract_request.response_schema
        record_type = schema_cls.model_fields["records"].annotation
        args = typing.get_args(record_type)
        dynamic_record_cls = args[0] if args else None

        dummy_records = []
        count = 10
        for i in range(count):
            field_values = {}
            if dynamic_record_cls:
                for f_name in dynamic_record_cls.model_fields:
                    field_values[f_name] = f"{f_name.capitalize()} {i + 1}"
                dummy_record = dynamic_record_cls(**field_values)
                dummy_records.append(dummy_record)

        response_data = schema_cls(records=dummy_records)

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

    with patch(
        "app.seeder.ai.AIContractNormalizer.execute_contract", side_effect=mock_execute
    ) as mock_patch:
        yield mock_patch


@pytest.fixture
def temp_ddl_file(tmp_path: Path) -> Path:
    """Fixture creating a valid temporary SQL DDL file."""
    ddl_content = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        created_at TIMESTAMP
    );
    CREATE TABLE posts (
        id INT PRIMARY KEY,
        user_id INT REFERENCES users(id),
        title VARCHAR(255) NOT NULL
    );
    """
    file_path = tmp_path / "schema.sql"
    file_path.write_text(ddl_content, encoding="utf-8")
    return file_path


@pytest.fixture
def temp_invalid_ddl_file(tmp_path: Path) -> Path:
    """Fixture creating a temporary SQL DDL file that triggers validation failure (duplicate table)."""
    ddl_content = """
    CREATE TABLE users (
        id INT PRIMARY KEY
    );
    CREATE TABLE users (
        id INT PRIMARY KEY
    );
    """
    file_path = tmp_path / "invalid_schema.sql"
    file_path.write_text(ddl_content, encoding="utf-8")
    return file_path


@pytest.mark.asyncio
async def test_version_command() -> None:
    """Verify version command displays version information successfully."""
    app = CLIApplication()
    exit_code = await app.run(["version"])
    assert exit_code == ExitStatus.SUCCESS


@pytest.mark.asyncio
async def test_config_command() -> None:
    """Verify config command returns active configuration settings."""
    app = CLIApplication()
    exit_code = await app.run(["config"])
    assert exit_code == ExitStatus.SUCCESS


@pytest.mark.asyncio
async def test_health_command_healthy() -> None:
    """Verify health command outputs correct status when Redis is healthy."""
    app = CLIApplication()
    with (
        patch(
            "app.core.lifecycle.redis.redis_manager.check_health",
            new_callable=AsyncMock,
        ) as mock_health,
        patch("app.core.lifecycle.redis.redis_manager.connect", new_callable=AsyncMock),
        patch(
            "app.core.lifecycle.redis.redis_manager.disconnect", new_callable=AsyncMock
        ),
    ):
        mock_health.return_value = True
        exit_code = await app.run(["health"])
        assert exit_code == ExitStatus.SUCCESS


@pytest.mark.asyncio
async def test_health_command_unhealthy() -> None:
    """Verify health command outputs correct failure exit code when Redis is unhealthy."""
    app = CLIApplication()
    with (
        patch(
            "app.core.lifecycle.redis.redis_manager.check_health",
            new_callable=AsyncMock,
        ) as mock_health,
        patch("app.core.lifecycle.redis.redis_manager.connect", new_callable=AsyncMock),
        patch(
            "app.core.lifecycle.redis.redis_manager.disconnect", new_callable=AsyncMock
        ),
    ):
        mock_health.return_value = False
        exit_code = await app.run(["health"])
        assert exit_code == ExitStatus.RUNTIME_ERROR


@pytest.mark.asyncio
async def test_validate_command_success(temp_ddl_file: Path) -> None:
    """Verify schema validation command succeeds for a correct DDL schema."""
    app = CLIApplication()
    exit_code = await app.run(["validate", str(temp_ddl_file)])
    assert exit_code == ExitStatus.SUCCESS


@pytest.mark.asyncio
async def test_validate_command_failure(temp_invalid_ddl_file: Path) -> None:
    """Verify schema validation command fails for an incorrect DDL schema."""
    app = CLIApplication()
    exit_code = await app.run(["validate", str(temp_invalid_ddl_file)])
    assert exit_code == ExitStatus.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_plan_command_success(temp_ddl_file: Path) -> None:
    """Verify plan command creates a valid topologically ordered plan."""
    app = CLIApplication()
    exit_code = await app.run(["plan", str(temp_ddl_file)])
    assert exit_code == ExitStatus.SUCCESS


@pytest.mark.asyncio
async def test_generate_command_success(temp_ddl_file: Path) -> None:
    """Verify generate command executes topological generation successfully (dry run)."""
    app = CLIApplication()
    exit_code = await app.run(["generate", str(temp_ddl_file), "--num-records", "5"])
    assert exit_code == ExitStatus.SUCCESS


@pytest.mark.asyncio
async def test_export_command_success(temp_ddl_file: Path, tmp_path: Path) -> None:
    """Verify export command generates data and serializes output to disk."""
    app = CLIApplication()
    out_dir = tmp_path / "export_output"
    exit_code = await app.run(
        [
            "export",
            str(temp_ddl_file),
            "--export-format",
            "json",
            "--output-dir",
            str(out_dir),
            "--num-records",
            "2",
            "--seed",
            "42",
            "--row-targets",
            "users=3,posts=1",
        ]
    )
    assert exit_code == ExitStatus.SUCCESS

    # Verify dataset.json was created
    dataset_file = out_dir / "dataset.json"
    assert dataset_file.exists()

    # Verify counts inside dataset.json
    dataset_data = json.loads(dataset_file.read_text(encoding="utf-8"))
    assert "users" in dataset_data
    assert "posts" in dataset_data
    assert len(dataset_data["users"]) == 3
    assert len(dataset_data["posts"]) == 1


@pytest.mark.asyncio
async def test_pipeline_command_success(temp_ddl_file: Path, tmp_path: Path) -> None:
    """Verify pipeline command executes E2E pipeline successfully."""
    app = CLIApplication()
    out_dir = tmp_path / "pipeline_output"
    exit_code = await app.run(
        [
            "pipeline",
            str(temp_ddl_file),
            "--export-format",
            "csv",
            "--output-dir",
            str(out_dir),
            "--num-records",
            "2",
        ]
    )
    assert exit_code == ExitStatus.SUCCESS

    # Verify files created
    users_file = out_dir / "users.csv"
    posts_file = out_dir / "posts.csv"
    assert users_file.exists()
    assert posts_file.exists()


@pytest.mark.asyncio
async def test_configuration_overrides(temp_ddl_file: Path) -> None:
    """Verify global CLI configuration profile overrides behavior."""
    app = CLIApplication()
    with patch(
        "app.config.manager.ConfigurationManager.load_configuration"
    ) as mock_load:
        exit_code = await app.run(
            [
                "--profile",
                "production",
                "validate",
                str(temp_ddl_file),
            ]
        )
        assert exit_code == ExitStatus.SUCCESS
        mock_load.assert_called_once()
        _, kwargs = mock_load.call_args
        assert kwargs["programmatic_overrides"] == {"app": {"app_env": "production"}}


@pytest.mark.asyncio
async def test_argument_parsing_errors() -> None:
    """Verify exit code on invalid CLI commands."""
    app = CLIApplication()
    with patch("sys.stderr"):
        exit_code = await app.run(["invalid_command_name"])
        assert exit_code == ExitStatus.VALIDATION_ERROR


@pytest.mark.asyncio
async def test_missing_ddl_file_error() -> None:
    """Verify that a missing DDL file prints an error to stderr and returns VALIDATION_ERROR."""
    app = CLIApplication()
    with patch("sys.stderr") as mock_stderr:
        exit_code = await app.run(["validate", "nonexistent_schema_file.sql"])
        assert exit_code == ExitStatus.VALIDATION_ERROR
        mock_stderr.write.assert_called_with(
            "Error: SQL DDL file 'nonexistent_schema_file.sql' not found.\n"
        )


@pytest.mark.asyncio
async def test_missing_config_file_error(temp_ddl_file: Path) -> None:
    """Verify that a missing configuration file prints an error to stderr and returns CONFIGURATION_ERROR."""
    app = CLIApplication()
    with patch("sys.stderr") as mock_stderr:
        exit_code = await app.run(
            [
                "--config-file",
                "nonexistent_config_file.json",
                "validate",
                str(temp_ddl_file),
            ]
        )
        assert exit_code == ExitStatus.CONFIGURATION_ERROR
        mock_stderr.write.assert_called_with(
            "Error: Configuration file 'nonexistent_config_file.json' not found.\n"
        )
