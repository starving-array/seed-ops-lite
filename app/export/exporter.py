import asyncio
import time
import uuid
from pathlib import Path
from typing import Any

from app.export.exceptions import ExportWriteException
from app.export.formats import SerializerRegistry
from app.export.models import ExportRequest, ExportResult, ExportStatistics
from app.export.telemetry import ExportTelemetry
from app.export.validator import ExportValidator
from app.workers.models import ExecutionUnit


def _write_file_to_disk(target_dir_str: str, key: str, data_bytes: bytes) -> str:
    """Helper writing file to disk synchronously. Executed via asyncio.to_thread."""
    target_path = Path(target_dir_str)
    target_path.mkdir(parents=True, exist_ok=True)
    file_path = target_path / key
    file_path.write_bytes(data_bytes)
    return str(file_path.resolve())


class ExportEngine:
    """Reusable ExportEngine serializing datasets and tracking execution telemetry."""

    def __init__(self, validator: ExportValidator | None = None) -> None:
        """Initialize ExportEngine with optional custom validator."""
        self.validator = validator or ExportValidator()

    async def export(self, request: ExportRequest) -> ExportResult:
        """Validate, serialize, and persist datasets based on configuration.

        Args:
            request: ExportRequest input parameters.

        Returns:
            ExportResult: Status outcome of the export operation.
        """
        start_time = time.perf_counter()
        execution_id = str(uuid.uuid4())

        # Extract metadata
        format_name = (
            request.format.value
            if hasattr(request.format, "value")
            else str(request.format)
        )
        table_count = len(request.records)

        ExportTelemetry.log_export_started(execution_id, format_name, table_count)

        created_files: list[str] = []
        try:
            # 1. Validate export readiness
            validation_errors = self.validator.validate(
                request.records,
                format_name,
                request.target_directory,
                request.options,
            )

            if validation_errors:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                stats = ExportStatistics(
                    total_records=sum(len(rows) for rows in request.records.values()),
                    total_tables=table_count,
                    file_size_bytes=0,
                    duration_ms=duration_ms,
                )
                result = ExportResult(
                    success=False,
                    serialized_data={},
                    output_files={},
                    statistics=stats,
                    errors=validation_errors,
                )
                ExportTelemetry.log_export_completed(
                    execution_id, False, stats, duration_ms
                )
                return result

            # 2. Retrieve serializer and format data
            serializer = SerializerRegistry.get(format_name)
            serialized_data = serializer.serialize(request.records, request.options)

            # 3. Write data to disk if target directory is specified
            output_files: dict[str, str] = {}
            total_size_bytes = 0

            for key, data_bytes in serialized_data.items():
                total_size_bytes += len(data_bytes)
                if request.target_directory:
                    file_path = Path(request.target_directory) / key
                    file_exists_before = await asyncio.to_thread(file_path.exists)

                    try:
                        resolved_path = await asyncio.to_thread(
                            _write_file_to_disk,
                            request.target_directory,
                            key,
                            data_bytes,
                        )
                        output_files[key] = resolved_path
                        if not file_exists_before:
                            created_files.append(resolved_path)
                    except Exception as e:
                        raise ExportWriteException(
                            f"Failed to write export file '{file_path}': {e!s}"
                        ) from e

            # Calculate metrics
            total_records = sum(len(rows) for rows in request.records.values())
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            stats = ExportStatistics(
                total_records=total_records,
                total_tables=table_count,
                file_size_bytes=total_size_bytes,
                duration_ms=duration_ms,
            )

            result = ExportResult(
                success=True,
                serialized_data=serialized_data,
                output_files=output_files,
                statistics=stats,
                errors=[],
            )

            ExportTelemetry.log_export_completed(execution_id, True, stats, duration_ms)
            return result

        except Exception as exc:
            if created_files:
                try:
                    await self._cleanup_files(created_files, execution_id)
                except Exception as cleanup_err:
                    ExportTelemetry.log_cleanup_failed(
                        execution_id, "all", str(cleanup_err)
                    )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            ExportTelemetry.log_export_failed(execution_id, str(exc), duration_ms)
            return ExportResult(
                success=False,
                serialized_data={},
                output_files={},
                statistics=ExportStatistics(duration_ms=duration_ms),
                errors=[str(exc)],
            )

    async def _cleanup_files(self, file_paths: list[str], execution_id: str) -> None:
        """Best-effort transactional cleanup of created files."""
        for path_str in file_paths:
            try:
                path = Path(path_str)
                if await asyncio.to_thread(path.exists):
                    await asyncio.to_thread(path.unlink)
            except Exception as e:
                ExportTelemetry.log_cleanup_failed(execution_id, path_str, str(e))

    async def execute_unit(self, unit: ExecutionUnit) -> dict[str, Any]:
        """Worker framework adapter mapping ExecutionUnit payload to ExportRequest and execution.

        Args:
            unit: The typed execution unit container.

        Returns:
            dict[str, Any]: Model dump of the ExportResult.
        """
        payload = unit.payload
        records = payload.get("records", {})
        format_val = payload.get("format", "json")
        target_directory = payload.get("target_directory")
        options = payload.get("options", {})

        request = ExportRequest(
            records=records,
            format=format_val,
            target_directory=target_directory,
            options=options,
        )

        result = await self.export(request)
        return result.model_dump()
