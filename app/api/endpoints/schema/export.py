import io
import json
import time
import zipfile
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from app.api.deps import get_redis
from app.api.endpoints.schema.helpers import (
    RedisType,
    _safe_decode,
    update_job,
)
from app.schemas.schema_design import (
    ExportSettingsModel,
    JobModel,
)

router = APIRouter()


async def run_export_background(
    export_job_id: str,
    export_settings: ExportSettingsModel,
    db_client: RedisType,
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
        )

        # Fetch generated records from Redis
        records_bytes = await db_client.get(
            f"generation:{export_settings.workflow_id}:records"
        )
        if not records_bytes:
            raise Exception(
                f"No generated dataset records found for session {export_settings.workflow_id}"
            )

        all_records = json.loads(_safe_decode(records_bytes))

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

        # Store result in Redis
        import hashlib

        checksum = hashlib.sha256(file_bytes).hexdigest()

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

        # Complete Job
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
            },
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
        )


@router.get("/export/datasets", response_model=list[dict[str, Any]])
async def list_exportable_datasets(
    db: RedisType = Depends(get_redis),
) -> list[dict[str, Any]]:
    """Lists completed generation jobs whose generated datasets are available for export."""
    job_ids_bytes = await db.smembers("jobs:all_ids")
    job_ids = [_safe_decode(j) for j in job_ids_bytes] if job_ids_bytes else []

    datasets = []
    for j_id in job_ids:
        job_bytes = await db.get(f"jobs:{j_id}")
        if job_bytes:
            job_dict = json.loads(_safe_decode(job_bytes))
            if (
                job_dict.get("type") == "generation"
                and job_dict.get("status") == "Completed"
            ):
                gen_bytes = await db.get(f"generation:{j_id}:status")
                progress_list = []
                total_rows = 0
                if gen_bytes:
                    gen_dict = json.loads(_safe_decode(gen_bytes))
                    progress_list = gen_dict.get("progress", [])
                    total_rows = gen_dict.get("totalRowsGenerated", 0)

                datasets.append(
                    {
                        "workflowId": j_id,
                        "startedAt": job_dict.get("startedAt"),
                        "finishedAt": job_dict.get("finishedAt"),
                        "totalRowsGenerated": total_rows,
                        "resultSummary": job_dict.get("resultSummary"),
                        "progress": progress_list,
                    }
                )

    datasets.sort(key=lambda x: x["startedAt"], reverse=True)
    return datasets


@router.post("/export", response_model=JobModel)
async def start_export_job(
    request: ExportSettingsModel,
    background_tasks: BackgroundTasks,
    db: RedisType = Depends(get_redis),
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
    )

    background_tasks.add_task(run_export_background, export_job_id, request, db)

    job_bytes = await db.get(f"jobs:{export_job_id}")
    assert job_bytes is not None
    job_dict = json.loads(_safe_decode(job_bytes))
    return JobModel(**job_dict)


@router.get("/export/{export_job_id}/download")
async def download_exported_file(
    export_job_id: str,
    db: RedisType = Depends(get_redis),
) -> Response:
    """Retrieves and downloads the serialized data file for a completed export job."""
    payload_bytes = await db.get(f"export:{export_job_id}:payload")
    if not payload_bytes:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Exported payload not found or expired for session "
                f"{export_job_id}."
            ),
        )

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
