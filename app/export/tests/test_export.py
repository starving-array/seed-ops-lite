import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.export.exporter import ExportEngine
from app.export.formats import FormatSerializer, SerializerRegistry
from app.export.models import ExportFormat, ExportRequest
from app.export.validator import ExportValidator
from app.workers.models import ExecutionUnit


@pytest.fixture
def sample_dataset() -> dict[str, list[dict[str, Any]]]:
    return {
        "users": [
            {"id": 1, "name": "Alice", "role": "admin"},
            {"id": 2, "name": "Bob", "role": "user"},
        ],
        "posts": [
            {"id": 101, "user_id": 1, "title": "Post A"},
            {"id": 102, "user_id": 2, "title": "Post B"},
        ],
    }


@pytest.mark.asyncio
async def test_json_export_in_memory(sample_dataset) -> None:
    engine = ExportEngine()
    request = ExportRequest(
        records=sample_dataset,
        format=ExportFormat.JSON,
        options={"indent": 4},
    )
    result = await engine.export(request)

    assert result.success
    assert "dataset.json" in result.serialized_data

    serialized_bytes = result.serialized_data["dataset.json"]
    deserialized = json.loads(serialized_bytes.decode("utf-8"))

    assert deserialized == sample_dataset
    assert result.statistics.total_records == 4
    assert result.statistics.total_tables == 2
    assert result.statistics.file_size_bytes > 0


@pytest.mark.asyncio
async def test_csv_export_in_memory(sample_dataset) -> None:
    engine = ExportEngine()
    request = ExportRequest(
        records=sample_dataset,
        format=ExportFormat.CSV,
        options={"delimiter": ";"},
    )
    result = await engine.export(request)

    assert result.success
    assert "users.csv" in result.serialized_data
    assert "posts.csv" in result.serialized_data

    users_csv = result.serialized_data["users.csv"].decode("utf-8")
    posts_csv = result.serialized_data["posts.csv"].decode("utf-8")

    assert "id;name;role" in users_csv
    assert "1;Alice;admin" in users_csv
    assert "id;user_id;title" in posts_csv
    assert "101;1;Post A" in posts_csv


@pytest.mark.asyncio
async def test_export_to_disk(sample_dataset) -> None:
    temp_dir = tempfile.mkdtemp()
    try:
        engine = ExportEngine()
        request = ExportRequest(
            records=sample_dataset,
            format=ExportFormat.CSV,
            target_directory=temp_dir,
        )
        result = await engine.export(request)

        assert result.success
        assert len(result.output_files) == 2

        users_path = Path(result.output_files["users.csv"])
        posts_path = Path(result.output_files["posts.csv"])

        assert users_path.exists()
        assert posts_path.exists()

        content = users_path.read_text(encoding="utf-8")
        assert "Alice" in content

    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_validator_dataset_completeness() -> None:
    validator = ExportValidator()

    # Empty dataset
    errors = validator.validate({}, "json")
    assert any("is empty" in err for err in errors)

    # Invalid dataset type
    errors = validator.validate([], "json")  # type: ignore
    assert any("must be a dictionary" in err for err in errors)


@pytest.mark.asyncio
async def test_validator_schema_consistency() -> None:
    validator = ExportValidator()

    inconsistent_records = {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob", "extra_field": "mismatch"},
        ]
    }

    errors = validator.validate(inconsistent_records, "json")
    assert any("Schema inconsistency" in err for err in errors)


@pytest.mark.asyncio
async def test_validator_csv_nested_structure() -> None:
    validator = ExportValidator()

    nested_records = {"users": [{"id": 1, "profile": {"bio": "hello"}}]}

    errors = validator.validate(nested_records, "csv")
    assert any("nested structure" in err for err in errors)


@pytest.mark.asyncio
async def test_unsupported_format_raises() -> None:
    engine = ExportEngine()
    request = ExportRequest(
        records={"users": []},
        format="unsupported",  # type: ignore
    )
    result = await engine.export(request)
    assert not result.success
    assert any("Unsupported export format" in err for err in result.errors)


@pytest.mark.asyncio
async def test_custom_serializer_registration() -> None:
    class UpperCaseSerializer(FormatSerializer):
        def serialize(
            self,
            records: dict[str, list[dict[str, Any]]],
            _options: dict[str, Any] | None = None,
        ) -> dict[str, bytes]:
            return {"upper.txt": str(records).upper().encode("utf-8")}

    SerializerRegistry.register("upper", UpperCaseSerializer)

    engine = ExportEngine()
    request = ExportRequest(
        records={"users": [{"id": 1, "name": "Alice"}]},
        format="upper",  # type: ignore
    )
    result = await engine.export(request)

    assert result.success
    assert "upper.txt" in result.serialized_data
    assert b"ALICE" in result.serialized_data["upper.txt"]


@pytest.mark.asyncio
async def test_worker_framework_integration(sample_dataset) -> None:
    engine = ExportEngine()

    unit = ExecutionUnit(
        unit_id="unit-export-789",
        task_type="export",
        target="db_export",
        payload={
            "records": sample_dataset,
            "format": "json",
            "options": {"indent": 0},
        },
    )

    result_dict = await engine.execute_unit(unit)
    assert result_dict["success"] is True
    assert "dataset.json" in result_dict["serialized_data"]


@pytest.mark.asyncio
async def test_successful_export_leaves_files_intact(sample_dataset) -> None:
    temp_dir = tempfile.mkdtemp()
    try:
        engine = ExportEngine()
        request = ExportRequest(
            records=sample_dataset,
            format=ExportFormat.CSV,
            target_directory=temp_dir,
        )
        result = await engine.export(request)
        assert result.success

        users_path = Path(temp_dir) / "users.csv"
        posts_path = Path(temp_dir) / "posts.csv"
        assert users_path.exists()
        assert posts_path.exists()
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_failure_during_export_removes_created_files(
    sample_dataset, monkeypatch
) -> None:
    from app.export import exporter as exporter_module

    temp_dir = tempfile.mkdtemp()
    try:
        original_write = exporter_module._write_file_to_disk

        # Succeed for users.csv but fail for posts.csv
        def mock_write(target_dir_str: str, key: str, data_bytes: bytes) -> str:
            if "posts" in key:
                raise OSError("Simulated write failure for posts")
            return original_write(target_dir_str, key, data_bytes)

        monkeypatch.setattr(exporter_module, "_write_file_to_disk", mock_write)

        engine = ExportEngine()
        request = ExportRequest(
            records=sample_dataset,
            format=ExportFormat.CSV,
            target_directory=temp_dir,
        )
        result = await engine.export(request)

        assert not result.success
        assert any("Simulated write failure" in err for err in result.errors)

        # Verify that users.csv was cleaned up
        users_path = Path(temp_dir) / "users.csv"
        assert not users_path.exists()
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_existing_files_are_preserved(sample_dataset, monkeypatch) -> None:
    from app.export import exporter as exporter_module

    temp_dir = tempfile.mkdtemp()
    try:
        # Pre-create users.csv which should be preserved
        users_path = Path(temp_dir) / "users.csv"
        users_path.write_text("pre-existing content", encoding="utf-8")

        original_write = exporter_module._write_file_to_disk

        # Fail for posts.csv
        def mock_write(target_dir_str: str, key: str, data_bytes: bytes) -> str:
            if "posts" in key:
                raise OSError("Simulated write failure for posts")
            return original_write(target_dir_str, key, data_bytes)

        monkeypatch.setattr(exporter_module, "_write_file_to_disk", mock_write)

        engine = ExportEngine()
        request = ExportRequest(
            records=sample_dataset,
            format=ExportFormat.CSV,
            target_directory=temp_dir,
        )
        result = await engine.export(request)

        assert not result.success

        # Verify users.csv is preserved (not deleted by cleanup)
        assert users_path.exists()
        # It was written to, but not cleaned up/deleted
        content = users_path.read_text(encoding="utf-8")
        assert "pre-existing content" not in content
        assert "Alice" in content
    finally:
        shutil.rmtree(temp_dir)


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_hide_exception_and_logs(
    sample_dataset, monkeypatch
) -> None:
    from app.export import exporter as exporter_module
    from app.export.telemetry import ExportTelemetry

    temp_dir = tempfile.mkdtemp()
    try:
        original_write = exporter_module._write_file_to_disk

        # Fail for posts.csv
        def mock_write(target_dir_str: str, key: str, data_bytes: bytes) -> str:
            if "posts" in key:
                raise OSError("Simulated write failure for posts")
            return original_write(target_dir_str, key, data_bytes)

        monkeypatch.setattr(exporter_module, "_write_file_to_disk", mock_write)

        # Fail unlink during cleanup
        def mock_unlink(*_args, **_kwargs):
            raise OSError("Simulated unlink failure")

        monkeypatch.setattr(Path, "unlink", mock_unlink)

        cleanup_failures = []

        def mock_log_cleanup(_execution_id, file_path, error_msg):
            cleanup_failures.append((file_path, error_msg))

        monkeypatch.setattr(ExportTelemetry, "log_cleanup_failed", mock_log_cleanup)

        engine = ExportEngine()
        request = ExportRequest(
            records=sample_dataset,
            format=ExportFormat.CSV,
            target_directory=temp_dir,
        )
        result = await engine.export(request)

        # Verify original exception is propagated inside result
        assert not result.success
        assert any("Simulated write failure" in err for err in result.errors)

        # Verify telemetry warning was logged
        assert len(cleanup_failures) == 1
        assert "Simulated unlink failure" in cleanup_failures[0][1]
    finally:
        shutil.rmtree(temp_dir)
