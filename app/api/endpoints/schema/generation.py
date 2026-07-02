import json
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_redis
from app.api.endpoints.schema.helpers import (
    RedisType,
    _safe_decode,
    update_job,
)
from app.api.endpoints.schema.validation import generate_ddl_from_schema
from app.schemas.schema_design import (
    GenerateRequestModel,
    GenerateResponseModel,
    SchemaModel,
    TableProgressModel,
)

router = APIRouter()


async def run_generation_background(
    workflow_id: str,
    schema: SchemaModel,
    row_targets: dict[str, int],
    seed: int | None,
    batch_size: int,
    _output_format: str,
    db_client: RedisType,
) -> None:
    import asyncio
    import json
    import time
    from datetime import datetime

    from app.seeder.models import SeedRequest
    from app.seeder.seeder import HybridSeeder

    start_time = time.perf_counter()
    seeder = HybridSeeder()

    table_map = {t.name: t for t in schema.tables}

    try:
        # Generate DDL to feed to GuardianPlanner for topological sort
        ddl = generate_ddl_from_schema(schema)
        from app.agents.schema_validation.models import SchemaValidationReport

        report = SchemaValidationReport(
            overall_status="pass",
            summary="Pre-check passed",
            findings=[],
            recommendations=[],
            warnings=[],
            execution_statistics={},
            executed_skills=[],
            execution_duration_ms=0.0,
        )
        from app.agents.guardian.planner import GuardianPlanner

        planner = GuardianPlanner()
        plan_result = await planner.plan(ddl, report, row_targets)
        ordered_tables = plan_result.ordered_tables
    except Exception:
        ordered_tables = [t.name for t in schema.tables]

    progress_map = {
        t_name: {
            "tableName": t_name,
            "status": "Pending",
            "rowsGenerated": 0,
            "targetRows": row_targets.get(t_name, 100),
            "error": None,
        }
        for t_name in ordered_tables
    }

    status_dict: dict[str, Any] = {
        "workflowId": workflow_id,
        "status": "Running",
        "totalRowsGenerated": 0,
        "durationMs": 0.0,
        "errors": [],
        "progress": list(progress_map.values()),
        "downloadPlaceholder": None,
        "startTime": start_time,
    }

    await db_client.set(
        f"generation:{workflow_id}:status",
        json.dumps(status_dict),
    )

    # Initialize statistics counters
    total_records_gen = 0
    successful_records_gen = 0
    failed_records_gen = 0
    deterministic_fields_count_gen = 0
    ai_fields_count_gen = 0
    prompt_tokens_gen = 0
    completion_tokens_gen = 0
    total_tokens_gen = 0
    estimated_cost_gen = 0.0
    latency_ms_gen = 0.0

    def get_metadata_details() -> dict[str, Any]:
        return {
            "progress": list(progress_map.values()),
            "generatedSeed": seed,
            "selectedBatchSize": batch_size,
            "batchSelectionStrategy": "Auto",
            "statistics": {
                "totalRecords": total_records_gen,
                "successfulRecords": successful_records_gen,
                "failedRecords": failed_records_gen,
                "deterministicFieldsCount": deterministic_fields_count_gen,
                "aiFieldsCount": ai_fields_count_gen,
                "promptTokens": prompt_tokens_gen,
                "completionTokens": completion_tokens_gen,
                "totalTokens": total_tokens_gen,
                "estimatedCost": estimated_cost_gen,
                "latencyMs": latency_ms_gen,
            },
        }

    # Move Job status to Running
    await update_job(
        db_client,
        job_id=workflow_id,
        status="Running",
        progress=0.0,
        details=get_metadata_details(),
    )

    all_records: dict[str, list[dict[str, Any]]] = {}
    total_rows_generated_acc = 0
    total_records_to_generate = sum(row_targets.get(t, 100) for t in ordered_tables)
    errors = []
    generation_cancelled = False

    try:
        for t_name in ordered_tables:
            # Check for cancellation
            cancel_flag = await db_client.get(f"generation:{workflow_id}:cancel")
            if cancel_flag and _safe_decode(cancel_flag) == "true":
                generation_cancelled = True
                break

            progress_map[t_name]["status"] = "Running"
            status_dict["progress"] = list(progress_map.values())
            status_dict["durationMs"] = round(
                (time.perf_counter() - start_time) * 1000.0, 2
            )
            await db_client.set(
                f"generation:{workflow_id}:status",
                json.dumps(status_dict),
            )

            table_obj = table_map.get(t_name)
            if not table_obj:
                raise Exception(f"Table {t_name} not found in schema")

            target_rows = row_targets.get(t_name, 100)

            # Reconstruct FieldDefinitions
            from app.cli.runner import map_column_to_field_def

            fields = {}
            for col in table_obj.columns:
                fields[col.name] = map_column_to_field_def(
                    col.name, col.type, col.is_primary_key
                )

            curr_batch_size = batch_size if batch_size > 0 else 100
            rows_generated_for_table = 0

            while rows_generated_for_table < target_rows:
                # Check for cancellation inside batch loop
                cancel_flag = await db_client.get(f"generation:{workflow_id}:cancel")
                if cancel_flag and _safe_decode(cancel_flag) == "true":
                    generation_cancelled = True
                    break

                batch_limit = min(
                    curr_batch_size, target_rows - rows_generated_for_table
                )
                seed_req = SeedRequest(
                    target=t_name,
                    num_records=batch_limit,
                    fields=fields,
                    seed=seed,
                    strict=True,
                )

                seed_res = await seeder.seed(seed_req)
                if not seed_res.success:
                    raise Exception(
                        f"Seeder failed to generate records for table {t_name}"
                    )

                # Accumulate statistics if available
                if seed_res.statistics:
                    stats = seed_res.statistics
                    total_records_gen += stats.total_records
                    successful_records_gen += stats.successful_records
                    failed_records_gen += stats.failed_records
                    deterministic_fields_count_gen += stats.deterministic_fields_count
                    ai_fields_count_gen += stats.ai_fields_count
                    prompt_tokens_gen += stats.prompt_tokens
                    completion_tokens_gen += stats.completion_tokens
                    total_tokens_gen += stats.total_tokens
                    estimated_cost_gen += stats.estimated_cost
                    latency_ms_gen += stats.latency_ms

                all_records.setdefault(t_name, []).extend(
                    [r.data for r in seed_res.records]
                )

                rows_generated_for_table += batch_limit
                total_rows_generated_acc += batch_limit

                pct = (
                    (total_rows_generated_acc / total_records_to_generate) * 100.0
                    if total_records_to_generate > 0
                    else 0.0
                )
                elapsed = time.perf_counter() - start_time

                progress_map[t_name]["rowsGenerated"] = rows_generated_for_table
                status_dict["totalRowsGenerated"] = total_rows_generated_acc
                status_dict["progress"] = list(progress_map.values())
                status_dict["durationMs"] = round(elapsed * 1000.0, 2)
                await db_client.set(
                    f"generation:{workflow_id}:status",
                    json.dumps(status_dict),
                )

                # Update Job progress
                await update_job(
                    db_client,
                    job_id=workflow_id,
                    status="Running",
                    progress=pct,
                    duration=elapsed,
                    details=get_metadata_details(),
                )

                await asyncio.sleep(0.02)

            if generation_cancelled:
                break

            progress_map[t_name]["status"] = "Completed"
            status_dict["progress"] = list(progress_map.values())
            await db_client.set(
                f"generation:{workflow_id}:status",
                json.dumps(status_dict),
            )

        if generation_cancelled:
            for t_name in ordered_tables:
                if progress_map[t_name]["status"] in ("Pending", "Running"):
                    progress_map[t_name]["status"] = "Failed"
                    progress_map[t_name]["error"] = "Generation cancelled by user"

            status_dict["status"] = "Failed"
            status_dict["errors"].append("Generation cancelled by user.")
            status_dict["progress"] = list(progress_map.values())
            status_dict["durationMs"] = round(
                (time.perf_counter() - start_time) * 1000.0, 2
            )
            await db_client.set(
                f"generation:{workflow_id}:status",
                json.dumps(status_dict),
            )

            # Move Job to Cancelled
            pct = (
                (total_rows_generated_acc / total_records_to_generate) * 100.0
                if total_records_to_generate > 0
                else 0.0
            )
            elapsed = time.perf_counter() - start_time
            await update_job(
                db_client,
                job_id=workflow_id,
                status="Cancelled",
                progress=pct,
                duration=elapsed,
                finished_at=datetime.utcnow().isoformat() + "Z",
                result_summary="Generation cancelled by user.",
                details=get_metadata_details(),
            )
        else:
            status_dict["status"] = "Completed"
            status_dict["downloadPlaceholder"] = (
                f"/schema/generate/{workflow_id}/download"
            )
            status_dict["durationMs"] = round(
                (time.perf_counter() - start_time) * 1000.0, 2
            )
            await db_client.set(
                f"generation:{workflow_id}:status",
                json.dumps(status_dict),
            )
            await db_client.set(
                f"generation:{workflow_id}:records",
                json.dumps(all_records),
            )

            # Move Job to Completed
            elapsed = time.perf_counter() - start_time
            await update_job(
                db_client,
                job_id=workflow_id,
                status="Completed",
                progress=100.0,
                duration=elapsed,
                finished_at=datetime.utcnow().isoformat() + "Z",
                result_summary=f"Successfully generated {total_rows_generated_acc} rows.",
                details=get_metadata_details(),
            )

    except Exception as e:
        errors.append(str(e))
        for t_name in ordered_tables:
            if progress_map[t_name]["status"] in ("Pending", "Running"):
                progress_map[t_name]["status"] = "Failed"
                progress_map[t_name]["error"] = str(e)

        status_dict["status"] = "Failed"
        status_dict["errors"] = errors
        status_dict["progress"] = list(progress_map.values())
        status_dict["durationMs"] = round(
            (time.perf_counter() - start_time) * 1000.0, 2
        )
        await db_client.set(
            f"generation:{workflow_id}:status",
            json.dumps(status_dict),
        )

        # Move Job to Failed
        pct = (
            (total_rows_generated_acc / total_records_to_generate) * 100.0
            if total_records_to_generate > 0
            else 0.0
        )
        elapsed = time.perf_counter() - start_time
        await update_job(
            db_client,
            job_id=workflow_id,
            status="Failed",
            progress=pct,
            duration=elapsed,
            finished_at=datetime.utcnow().isoformat() + "Z",
            error_message=str(e),
            result_summary=f"Generation failed: {e!s}",
            details=get_metadata_details(),
        )


@router.post("/generate", response_model=GenerateResponseModel)
async def start_generation(
    request: GenerateRequestModel,
    background_tasks: BackgroundTasks,
    db: RedisType = Depends(get_redis),
) -> GenerateResponseModel:
    """Starts synthetic data generation as a background workflow task."""
    import random
    import uuid
    from datetime import datetime

    from app.seeder.batch_engine import calculate_batch_size

    workflow_id = str(uuid.uuid4())

    # Always auto-generate seed internally
    seed = random.randint(1, 1000000)  # noqa: S311

    # Auto-calculate batch size
    batch_size = calculate_batch_size(request.schema_state, request.row_targets)

    # Initialize Queued status in Redis
    progress = [
        TableProgressModel(
            tableName=t.name,
            status="Pending",
            rowsGenerated=0,
            targetRows=request.row_targets.get(t.name, 100),
        )
        for t in request.schema_state.tables
    ]

    initial_status = GenerateResponseModel(
        workflowId=workflow_id,
        status="Queued",
        progress=progress,
        totalRowsGenerated=0,
        durationMs=0.0,
        errors=[],
    )

    await db.set(
        f"generation:{workflow_id}:status",
        json.dumps(initial_status.model_dump(by_alias=True)),
    )

    # Initialize Job in history as Queued
    await update_job(
        db,
        job_id=workflow_id,
        job_type="generation",
        status="Queued",
        progress=0.0,
        started_at=datetime.utcnow().isoformat() + "Z",
        result_summary="Scheduled synthetic data generation.",
        details={
            "progress": [p.model_dump(by_alias=True) for p in progress],
            "generatedSeed": seed,
            "selectedBatchSize": batch_size,
            "batchSelectionStrategy": "Auto",
        },
    )

    # Run the generation background task
    background_tasks.add_task(
        run_generation_background,
        workflow_id,
        request.schema_state,
        request.row_targets,
        seed,
        batch_size,
        request.output_format,
        db,
    )

    return initial_status


@router.get("/generate/{workflow_id}", response_model=GenerateResponseModel)
async def get_generation_status(
    workflow_id: str,
    db: RedisType = Depends(get_redis),
) -> GenerateResponseModel:
    """Retrieves progress and current status of an active or completed generation workflow."""
    status_bytes = await db.get(f"generation:{workflow_id}:status")
    if not status_bytes:
        raise HTTPException(
            status_code=404, detail="Generation workflow session not found."
        )

    status_dict = json.loads(_safe_decode(status_bytes))

    # Dynamically update duration_ms if it's still running
    if status_dict.get("status") == "Running" and "startTime" in status_dict:
        elapsed = (time.perf_counter() - status_dict["startTime"]) * 1000.0
        status_dict["durationMs"] = round(elapsed, 2)

    return GenerateResponseModel(**status_dict)


@router.post("/generate/{workflow_id}/cancel")
async def cancel_generation(
    workflow_id: str,
    db: RedisType = Depends(get_redis),
) -> dict[str, str]:
    """Signals cancellation to an active synthetic data generation run."""
    from datetime import datetime

    # Check if workflow exists
    status_bytes = await db.get(f"generation:{workflow_id}:status")
    if not status_bytes:
        raise HTTPException(
            status_code=404, detail="Generation workflow session not found."
        )

    # Write cancel flag
    await db.set(f"generation:{workflow_id}:cancel", "true")

    # Update Job immediately to Cancelled
    await update_job(
        db,
        job_id=workflow_id,
        status="Cancelled",
        finished_at=datetime.utcnow().isoformat() + "Z",
        result_summary="Generation cancelled by user.",
    )

    return {
        "status": "success",
        "message": "Cancellation signal sent successfully.",
    }


@router.get("/generate/{workflow_id}/preview")
async def get_preview_data(
    workflow_id: str,
    db: RedisType = Depends(get_redis),
) -> dict[str, Any]:
    """Retrieve generated records from Redis for UI preview."""
    records_bytes = await db.get(f"generation:{workflow_id}:records")
    if not records_bytes:
        raise HTTPException(
            status_code=404, detail="No generated records found for this session."
        )
    try:
        res = json.loads(_safe_decode(records_bytes))
        if isinstance(res, dict):
            return res
        return {}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to decode generated data: {e!s}"
        ) from e


@router.get("/generate/{workflow_id}/download")
async def download_generated_data(
    workflow_id: str,
    db: RedisType = Depends(get_redis),
) -> dict[str, Any]:
    """Download placeholder returning generated data stats."""
    status_bytes = await db.get(f"generation:{workflow_id}:status")
    if not status_bytes:
        raise HTTPException(
            status_code=404, detail="Generation workflow session not found."
        )

    status_dict = json.loads(_safe_decode(status_bytes))
    return {
        "status": "success",
        "message": "Synthetic dataset generation complete.",
        "workflowId": workflow_id,
        "totalRowsGenerated": status_dict.get("totalRowsGenerated", 0),
        "durationMs": status_dict.get("durationMs", 0.0),
        "data_format": "json",
    }
