import contextlib
import io
import json
import time
import zipfile
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from app.api.deps import get_runtime_provider
from app.api.endpoints.schema.helpers import (
    RuntimeProviderType,
    _safe_decode,
    update_job,
)
from app.platform.container import get_persistence_provider
from app.platform.persistence.interfaces import PersistenceProvider
from app.schemas.schema_design import (
    ExportSettingsModel,
    JobModel,
)

router = APIRouter()


async def run_export_background(
    export_job_id: str,
    export_settings: ExportSettingsModel,
    db_client: RuntimeProviderType,
    persistence: PersistenceProvider,
) -> None:
    from app.export.exporter import ExportEngine
    from app.export.models import ExportRequest

    start_time = time.perf_counter()

    try:
        # Step Preparing
        await update_job(
            db_client,
            job_id=export_job_id,
            job_type="export",
            status="Running",
            progress=20.0,
            result_summary="Preparing dataset for export...",
            details={"step": "Preparing"},
            persistence=persistence,
        )

        # Fetch generated records — try RuntimeProvider preview cache first, then disk
        all_records: dict[str, list[Any]] = {}
        loaded_from_cache = False
        with contextlib.suppress(Exception):
            records_bytes = await db_client.get(
                f"generation:{export_settings.workflow_id}:records"
            )
            if records_bytes:
                cached = json.loads(_safe_decode(records_bytes))
                if isinstance(cached, dict) and cached:
                    all_records = cached
                    loaded_from_cache = True

        if not loaded_from_cache:
            # Fall back to DiskDatasetStorageManager (authoritative Parquet store)
            from app.platform.container import get_dataset_storage_manager

            ds_manager = get_dataset_storage_manager()
            manifest = await ds_manager.get_dataset_metadata(
                export_settings.workflow_id
            )
            if not manifest:
                raise Exception(
                    f"No generated dataset records found for session {export_settings.workflow_id}. "
                    "Parquet files not found on disk."
                )
            for table_info in manifest.get("tables", []):
                t_name = table_info["name"]
                try:
                    rows = await ds_manager.read_table_dataset_preview(
                        export_settings.workflow_id, t_name, limit=100_000
                    )
                    all_records[t_name] = rows
                except Exception as exc:
                    from app.core.logging.logging import logger
                    from app.telemetry.events import EventID

                    logger.error(
                        EventID.LOG_ERROR,
                        f"Failed to read table {t_name} from disk for export",
                        error=str(exc),
                    )

        if not all_records:
            raise Exception(
                f"No generated dataset records found for session {export_settings.workflow_id}."
            )

        # Filter tables to export if specified
        if export_settings.tables:
            records = {
                t: all_records[t] for t in export_settings.tables if t in all_records
            }
        else:
            records = all_records

        if not records:
            raise Exception("No records matching the selected tables were found.")

        # Step Exporting
        await update_job(
            db_client,
            job_id=export_job_id,
            status="Running",
            progress=50.0,
            result_summary="Serializing dataset formats...",
            details={"step": "Exporting"},
            persistence=persistence,
        )

        # Invoke ExportEngine
        engine = ExportEngine()
        fmt = export_settings.format.lower()

        options = {"indent": 2, "delimiter": ","}

        export_req = ExportRequest(
            records=records,
            format=fmt,
            target_directory=None,
            options=options,
        )

        export_res = await engine.export(export_req)
        if not export_res.success:
            err_msg = export_res.errors[0] if export_res.errors else "Unknown error"
            raise Exception(f"Serializer failure: {err_msg}")

        # Step Packaging
        await update_job(
            db_client,
            job_id=export_job_id,
            status="Running",
            progress=80.0,
            result_summary="Packaging files for delivery...",
            details={"step": "Packaging"},
            persistence=persistence,
        )

        serialized_data = export_res.serialized_data
        zip_placeholder = export_settings.compression

        final_filename = f"dataset_{export_job_id[:8]}"
        if export_settings.file_name_convention == "timestamp":
            final_filename = f"export_{int(time.time())}"

        if zip_placeholder or len(serialized_data) > 1:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                if export_settings.include_metadata:
                    meta = {
                        "exportedAt": datetime.utcnow().isoformat() + "Z",
                        "format": fmt,
                        "tables": list(records.keys()),
                        "totalRecords": sum(len(rows) for rows in records.values()),
                    }
                    zip_file.writestr("metadata.json", json.dumps(meta, indent=2))

                for fname, fbytes in serialized_data.items():
                    zip_file.writestr(fname, fbytes)
            file_bytes = zip_buffer.getvalue()
            filename = f"{final_filename}.zip"
            mime_type = "application/zip"
        else:
            fname = next(iter(serialized_data.keys()))
            file_bytes = serialized_data[fname]
            ext = fname.split(".")[-1]
            filename = f"{final_filename}.{ext}"

            if ext == "json":
                mime_type = "application/json"
            elif ext == "csv":
                mime_type = "text/csv"
            elif ext == "sql":
                mime_type = "application/sql"
            else:
                mime_type = "application/octet-stream"

        import hashlib

        checksum = hashlib.sha256(file_bytes).hexdigest()

        # Store export payload in RuntimeProvider (ephemeral — used for download)
        export_payload = {
            "bytes": file_bytes.hex(),
            "filename": filename,
            "mimeType": mime_type,
            "fileSizeBytes": len(file_bytes),
            "checksum": checksum,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "format": fmt,
        }
        await db_client.set(
            f"export:{export_job_id}:payload",
            json.dumps(export_payload),
        )

        # Complete Job — durable write to SQLite
        elapsed = time.perf_counter() - start_time
        await update_job(
            db_client,
            job_id=export_job_id,
            status="Completed",
            progress=100.0,
            duration=elapsed,
            finished_at=datetime.utcnow().isoformat() + "Z",
            result_summary=(
                f"Dataset exported successfully as {fmt.upper()} "
                f"({len(file_bytes)} bytes)."
            ),
            details={
                "step": "Completed",
                "filename": filename,
                "fileSizeBytes": len(file_bytes),
                "checksum": checksum,
                "format": fmt,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "downloadPlaceholder": f"/schema/export/{export_job_id}/download",
                # Stored for disk-fallback recovery if RuntimeProvider cache expires
                "workflowId": export_settings.workflow_id,
            },
            persistence=persistence,
        )

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        await update_job(
            db_client,
            job_id=export_job_id,
            status="Failed",
            progress=100.0,
            duration=elapsed,
            finished_at=datetime.utcnow().isoformat() + "Z",
            error_message=str(e),
            result_summary=f"Export failed: {e!s}",
            details={"step": "Failed"},
            persistence=persistence,
        )


@router.get("/export/datasets", response_model=list[dict[str, Any]])
async def list_exportable_datasets(
    db: PersistenceProvider = Depends(get_persistence_provider),
    runtime: RuntimeProviderType = Depends(get_runtime_provider),
) -> list[dict[str, Any]]:
    """Lists completed generation jobs whose datasets are available for export.

    SQLite is the authoritative source — no Redis dependency for job listing.
    The RuntimeProvider is consulted only to fetch per-job row counts from
    the generation status cache (ephemeral metadata).
    """
    all_jobs = await db.list_jobs()

    datasets = []
    for job_dict in all_jobs:
        job_id = job_dict.get("jobId") or job_dict.get("id", "")
        if (
            job_dict.get("type") == "generation"
            and job_dict.get("status") == "Completed"
        ):
            # Try to get row count from RuntimeProvider generation status cache
            progress_list: list[Any] = []
            total_rows = 0
            with contextlib.suppress(Exception):
                gen_bytes = await runtime.get(f"generation:{job_id}:status")
                if gen_bytes:
                    gen_dict = json.loads(_safe_decode(gen_bytes))
                    progress_list = gen_dict.get("progress", [])
                    total_rows = gen_dict.get("totalRowsGenerated", 0)

            datasets.append(
                {
                    "workflowId": job_id,
                    "startedAt": job_dict.get("startedAt"),
                    "finishedAt": job_dict.get("finishedAt"),
                    "totalRowsGenerated": total_rows,
                    "resultSummary": job_dict.get("resultSummary"),
                    "progress": progress_list,
                }
            )

    datasets.sort(key=lambda x: x["startedAt"] or "", reverse=True)
    return datasets


@router.post("/export", response_model=JobModel)
async def start_export_job(
    request: ExportSettingsModel,
    background_tasks: BackgroundTasks,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> JobModel:
    """Starts a background export job for a generated dataset."""
    import uuid

    export_job_id = str(uuid.uuid4())

    await update_job(
        db,
        job_id=export_job_id,
        job_type="export",
        status="Queued",
        progress=0.0,
        started_at=datetime.utcnow().isoformat() + "Z",
        result_summary=(f"Preparing dataset export format {request.format.upper()}..."),
        persistence=persistence,
    )

    background_tasks.add_task(
        run_export_background, export_job_id, request, db, persistence
    )

    # Read the freshly-written job from SQLite for the response
    job_dict = await persistence.get_job(export_job_id)
    if job_dict is None:
        # Fallback to RuntimeProvider cache if SQLite write hasn't flushed yet
        job_bytes = await db.get(f"jobs:{export_job_id}")
        assert job_bytes is not None
        job_dict = json.loads(_safe_decode(job_bytes))

    return JobModel(**job_dict)


@router.get("/export/{export_job_id}/download")
async def download_exported_file(
    export_job_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> Response:
    """Retrieves and downloads the serialized data file for a completed export job.

    Resolution order:
    1. RuntimeProvider ephemeral payload cache (fast path).
    2. Re-stream from DiskDatasetStorageManager Parquet files (Redis-offline fallback).
    """
    # 1. Try RuntimeProvider cache (fast path)
    payload_bytes = None
    with contextlib.suppress(Exception):
        payload_bytes = await db.get(f"export:{export_job_id}:payload")

    if payload_bytes:
        payload = json.loads(_safe_decode(payload_bytes))
        file_bytes = bytes.fromhex(payload["bytes"])
        return Response(
            content=file_bytes,
            media_type=payload["mimeType"],
            headers={
                "Content-Disposition": f"attachment; filename={payload['filename']}",
                "Content-Length": str(payload["fileSizeBytes"]),
            },
        )

    # 2. Disk fallback — look up the job in SQLite to find the original generation workflow
    job_dict = await persistence.get_job(export_job_id)
    if not job_dict:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Export job {export_job_id} not found. "
                "The export payload has expired and the original job record was not found."
            ),
        )

    details = job_dict.get("details") or {}
    # The generation workflow_id is stored in the export request settings, not directly
    # in job details — fall back to a ZIP stream from DiskDatasetStorageManager if available.
    from app.platform.container import get_dataset_storage_manager

    ds_manager = get_dataset_storage_manager()

    # Attempt to find associated generation job via SQLite metadata
    # The export job may carry the workflow_id in result_summary or details
    workflow_id = details.get("workflowId") or details.get("workflow_id")

    if not workflow_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Exported payload not found or expired for export job {export_job_id}. "
                "Restart the export to regenerate the download."
            ),
        )

    manifest = await ds_manager.get_dataset_metadata(workflow_id)
    if not manifest:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Dataset files not found for workflow {workflow_id}. "
                "The dataset may have been purged from disk."
            ),
        )

    # Stream a fresh ZIP package from Parquet files

    zip_chunks = list(ds_manager.stream_multi_table_zip(workflow_id))
    file_bytes = b"".join(zip_chunks)
    filename = f"dataset_{workflow_id[:8]}.zip"

    return Response(
        content=file_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(file_bytes)),
        },
    )
