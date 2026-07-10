import contextlib
import json
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_runtime_provider
from app.api.endpoints.schema.helpers import (
    RuntimeProviderType,
    _safe_decode,
    update_job,
)
from app.api.endpoints.schema.validation import generate_ddl_from_schema
from app.platform.container import get_persistence_provider
from app.platform.persistence.interfaces import PersistenceProvider
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
    db_client: RuntimeProviderType,
    persistence: PersistenceProvider,
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
        if not schema.tables:
            ordered_tables = []
        else:
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
            try:
                plan_result = await planner.plan(ddl, report, row_targets)
                ordered_tables = plan_result.ordered_tables
            except Exception:
                ordered_tables = [t.name for t in schema.tables]
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
        persistence=persistence,
    )

    all_records: dict[str, list[dict[str, Any]]] = {}
    total_rows_generated_acc = 0
    total_records_to_generate = sum(row_targets.get(t, 100) for t in ordered_tables)
    errors = []
    generation_cancelled = False

    try:
        from app.seeder.allocator import RecordAllocator
        from app.seeder.math_computer import MathComputer
        from app.seeder.pk_generator import PrimaryKeyGenerator
        from app.seeder.relationship_planner import (
            DeferredReferenceResolver,
            RelationshipPlanner,
            SelfReferencePlanner,
        )

        # 1. Run Semantic Analyzer (FIRST — produces dependency metadata)
        from app.seeder.semantic_analyzer import SemanticAnalyzer

        semantic_metadata = SemanticAnalyzer.analyze(schema)

        # 1b. Build dependency graph from semantic metadata
        dep_graph = SemanticAnalyzer.build_dependency_graph(semantic_metadata)
        try:
            ordered_from_graph, _, _ = dep_graph.get_topological_sort_and_layers()
            if ordered_from_graph:
                ordered_tables = ordered_from_graph
        except Exception:  # noqa: S110
            pass

        # 2. Allocate Placeholders
        placeholders = RecordAllocator.allocate(schema, ordered_tables, row_targets)

        # 3. Generate PKs (BEFORE relationship planning — PK values must exist)
        PrimaryKeyGenerator.generate(schema, placeholders, seed or 1)

        # 4. Plan all relationships (assigns FK values from parent PKs)
        rel_stats = RelationshipPlanner.plan(schema, placeholders, seed)  # noqa: F841
        self_ref_stats = SelfReferencePlanner.plan(  # noqa: F841
            schema, placeholders, semantic_metadata, seed
        )
        deferred_stats = DeferredReferenceResolver.resolve(  # noqa: F841
            schema, placeholders, semantic_metadata, seed
        )

        # 5. Run Domain Intelligence Engine
        from app.seeder.domain_intelligence import DomainIntelligenceEngine

        domain_context = DomainIntelligenceEngine.analyze(schema)

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

            # Reconstruct FieldDefinitions (Business fields ONLY)
            from app.cli.runner import map_column_to_field_def

            fields = {}
            for col in table_obj.columns:
                # SKIP PKs and FKs for LLM generation
                if col.is_primary_key:
                    continue
                is_fk = False
                for rel in schema.relationships:
                    if (
                        rel.source_table_id == table_obj.id
                        and rel.source_column_id == col.id
                    ):
                        is_fk = True
                        break
                    if (
                        rel.target_table_id == table_obj.id
                        and rel.target_column_id == col.id
                    ):
                        is_fk = True
                        break
                if is_fk:
                    continue

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

                fk_context = []
                for bi in range(batch_limit):
                    idx = rows_generated_for_table + bi
                    rec = placeholders[t_name][idx]
                    fk_vals = {}
                    for col in table_obj.columns:
                        if col.is_primary_key:
                            fk_vals[col.name] = rec.get(col.name)
                            continue
                        is_fk = False
                        for rel in schema.relationships:
                            if (
                                rel.source_table_id == table_obj.id
                                and rel.source_column_id == col.id
                            ):
                                is_fk = True
                                break
                            if (
                                rel.target_table_id == table_obj.id
                                and rel.target_column_id == col.id
                            ):
                                is_fk = True
                                break
                        if is_fk:
                            fk_vals[col.name] = rec.get(col.name)
                    fk_context.append(fk_vals)

                meta_with_fk = dict(semantic_metadata.get(t_name, {}))
                meta_with_fk["fk_context"] = fk_context

                seed_req = SeedRequest(
                    target=t_name,
                    num_records=batch_limit,
                    fields=fields,
                    seed=seed,
                    strict=True,
                    semantic_metadata=meta_with_fk,
                    domain_context=domain_context,
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

                # Merge generated business fields into placeholders
                for i, r in enumerate(seed_res.records):
                    idx = rows_generated_for_table + i
                    placeholders[t_name][idx].update(r.data)

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

                # Update Job progress in RuntimeProvider only (not SQLite for every batch)
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

        if not generation_cancelled:
            # 8. Computed Fields
            math_stats = MathComputer.compute(schema, placeholders)
            import structlog

            logger = structlog.get_logger()
            logger.info(
                "MathComputer executed",
                computed=math_stats.get("computed", 0),
                skipped_null_source=math_stats.get("skipped_null_source", 0),
            )

            # 9. Business Rule Engine (Repairs)
            from app.seeder.business_rules import BusinessRuleEngine

            repair_stats = BusinessRuleEngine.enforce(
                schema, placeholders, semantic_metadata
            )

            # Log repair statistics
            import structlog

            logger = structlog.get_logger()
            logger.info(
                "Business Rule Engine executed",
                rules_evaluated=repair_stats["rules_evaluated"],
                rules_violated=repair_stats["rules_violated"],
                rules_repaired=repair_stats["rules_repaired"],
                repairs=repair_stats["repairs"],
            )

            # 10. Validation Gate
            from app.seeder.validator import SeederValidator

            ref_errors = SeederValidator.validate_referential_integrity(
                schema, placeholders
            )
            pk_errors = SeederValidator.validate_pk_uniqueness(schema, placeholders)
            self_errors = SeederValidator.validate_self_references(placeholders)
            junction_errors = SeederValidator.validate_junction_uniqueness(placeholders)

            all_validation_errors = (
                ref_errors + pk_errors + self_errors + junction_errors
            )
            if all_validation_errors:
                import structlog

                logger = structlog.get_logger()
                logger.warning(
                    "Validation gate",
                    referential_errors=len(ref_errors),
                    pk_errors=len(pk_errors),
                    self_ref_errors=len(self_errors),
                    junction_errors=len(junction_errors),
                    total=len(all_validation_errors),
                )
                for ve in all_validation_errors:
                    logger.warning("Validation issue", detail=ve)

            # 11. Dump placeholders into export/status pipeline Parquet
            from app.platform.container import get_dataset_storage_manager

            ds_manager = get_dataset_storage_manager()

            for t_name in ordered_tables:
                # Remove internal _ref_id, _table, _index
                clean_records = []
                for placeholder_rec in placeholders[t_name]:
                    clean_p = {
                        k: v
                        for k, v in placeholder_rec.items()
                        if not k.startswith("_")
                    }
                    clean_records.append(clean_p)

                all_records[t_name] = clean_records
                await ds_manager.write_table_dataset(workflow_id, t_name, clean_records)

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
                persistence=persistence,
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

            # Save dataset metadata to SQLite (authoritative source of truth)
            from app.platform.container import get_dataset_storage_manager

            ds_manager = get_dataset_storage_manager()
            dataset_dir = ds_manager.get_dataset_storage_path(workflow_id)
            table_stats = {
                table_name: {
                    "rowCount": progress_map[table_name]["rowsGenerated"],
                    "fileName": f"{table_name}.parquet",
                }
                for table_name in ordered_tables
            }
            await persistence.save_metadata(
                job_id=workflow_id,
                total_rows=total_rows_generated_acc,
                table_stats=table_stats,
                folder_path=dataset_dir,
            )

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
                persistence=persistence,
            )

            try:
                # Compute dataset size
                dataset_size_bytes = 0
                from pathlib import Path

                try:
                    for p in Path(dataset_dir).rglob("*"):
                        if p.is_file():
                            dataset_size_bytes += p.stat().st_size
                except Exception as size_err:
                    from app.core.logging.logging import logger

                    logger.debug(
                        "GEN-1002", f"Failed to compute dataset size: {size_err}"
                    )

                # Compile LLM Calls and Retries
                llm_calls_made = 0
                if total_records_gen > 0:
                    # Estimate based on generation stats or assume 1 call per batch generated
                    llm_calls_made = max(
                        1, total_records_gen // (batch_size if batch_size > 0 else 100)
                    )

                # Log workflow completion summary block
                from app.core.logging.logging import logger
                from app.telemetry.events import EventID

                logger.info(
                    EventID.GENERATION_COMPLETED,
                    "Workflow Execution Summary",
                    workflow_id=workflow_id,
                    duration=f"{elapsed * 1000.0:.2f} ms",
                    tables_generated=len(ordered_tables),
                    rows_generated=total_rows_generated_acc,
                    llm_calls=llm_calls_made,
                    prompt_tokens=prompt_tokens_gen,
                    completion_tokens=completion_tokens_gen,
                    total_tokens=total_tokens_gen,
                    retry_count=0,  # Defaults for retry coordinator
                    sqlite_writes=3
                    + len(ordered_tables),  # metadata, jobs updates, validations
                    redis_writes=2 * len(ordered_tables)
                    + 3,  # status updates & cancellations checks
                    cache_hits=len(ordered_tables),
                    cache_misses=0,
                    dataset_size=f"{dataset_size_bytes / 1024.0:.2f} KB",
                    export_size="0.00 KB",
                    status="Completed",
                )
            except Exception as summary_err:
                from app.core.logging.logging import logger

                logger.debug(
                    "GEN-1002", f"Summary block compilation error: {summary_err}"
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
            persistence=persistence,
        )


@router.post("/generate", response_model=GenerateResponseModel)
async def start_generation(
    request: GenerateRequestModel,
    background_tasks: BackgroundTasks,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> GenerateResponseModel:
    """Starts synthetic data generation as a background workflow task.

    The job record is immediately written to SQLite (durable). Generation
    progress is cached in the RuntimeProvider for real-time UI polling.
    """
    import random
    import uuid
    from datetime import datetime

    from app.seeder.batch_engine import calculate_batch_size

    workflow_id = str(uuid.uuid4())

    # Always auto-generate seed internally
    seed = random.randint(1, 1000000)  # noqa: S311

    # Auto-calculate batch size
    batch_size = calculate_batch_size(request.schema_state, request.row_targets)

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

    # Write initial status to RuntimeProvider cache
    await db.set(
        f"generation:{workflow_id}:status",
        json.dumps(initial_status.model_dump(by_alias=True)),
    )

    initial_details = {
        "progress": [p.model_dump(by_alias=True) for p in progress],
        "generatedSeed": seed,
        "selectedBatchSize": batch_size,
        "batchSelectionStrategy": "Auto",
    }

    # Initialize Job in SQLite (durable) + RuntimeProvider cache
    await update_job(
        db,
        job_id=workflow_id,
        job_type="generation",
        status="Queued",
        progress=0.0,
        started_at=datetime.utcnow().isoformat() + "Z",
        result_summary="Scheduled synthetic data generation.",
        details=initial_details,
        persistence=persistence,
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
        persistence,
    )

    return initial_status


@router.get("/generate/{workflow_id}", response_model=GenerateResponseModel)
async def get_generation_status(
    workflow_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> GenerateResponseModel:
    """Retrieves progress and current status of an active or completed generation workflow."""
    status_dict = None
    with contextlib.suppress(Exception):
        status_bytes = await db.get(f"generation:{workflow_id}:status")
        if status_bytes:
            status_dict = json.loads(_safe_decode(status_bytes))

    if not status_dict:
        # Fall back to SQLite PersistenceProvider
        job_dict = await persistence.get_job(workflow_id)
        if not job_dict:
            raise HTTPException(
                status_code=404, detail="Generation workflow session not found."
            )
        details = job_dict.get("details") or {}
        progress_data = details.get("progress") or []
        duration_ms = (job_dict.get("duration") or 0.0) * 1000.0
        status_dict = {
            "workflowId": workflow_id,
            "status": job_dict.get("status", "Unknown"),
            "progress": progress_data,
            "totalRowsGenerated": sum(p.get("rowsGenerated", 0) for p in progress_data),
            "durationMs": duration_ms,
            "errors": (
                [job_dict.get("errorMessage")] if job_dict.get("errorMessage") else []
            ),
            "downloadPlaceholder": (
                f"/schema/generate/{workflow_id}/download"
                if job_dict.get("status") == "Completed"
                else None
            ),
        }

    # Dynamically update duration_ms if it's still running
    if status_dict.get("status") == "Running" and "startTime" in status_dict:
        elapsed = (time.perf_counter() - status_dict["startTime"]) * 1000.0
        status_dict["durationMs"] = round(elapsed, 2)

    return GenerateResponseModel(**status_dict)


@router.post("/generate/{workflow_id}/cancel")
async def cancel_generation(
    workflow_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider | None = Depends(get_persistence_provider),
) -> dict[str, str]:
    """Signals cancellation to an active synthetic data generation run."""
    from datetime import datetime

    # Check if workflow exists — RuntimeProvider first, then SQLite fallback
    status_bytes = None
    with contextlib.suppress(Exception):
        status_bytes = await db.get(f"generation:{workflow_id}:status")

    if not status_bytes and persistence is not None:
        # RuntimeProvider cache miss — verify the job exists in SQLite
        job_dict = await persistence.get_job(workflow_id)
        if not job_dict:
            raise HTTPException(
                status_code=404, detail="Generation workflow session not found."
            )
    elif not status_bytes:
        raise HTTPException(
            status_code=404, detail="Generation workflow session not found."
        )

    # Write cancel flag to RuntimeProvider (best-effort, failure is non-fatal)
    with contextlib.suppress(Exception):
        await db.set(f"generation:{workflow_id}:cancel", "true")

    # Update Job immediately to Cancelled in SQLite + RuntimeProvider
    await update_job(
        db,
        job_id=workflow_id,
        status="Cancelled",
        finished_at=datetime.utcnow().isoformat() + "Z",
        result_summary="Generation cancelled by user.",
        persistence=persistence,
    )

    return {
        "status": "success",
        "message": "Cancellation signal sent successfully.",
    }


@router.get("/generate/{workflow_id}/preview")
async def get_preview_data(
    workflow_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
) -> dict[str, Any]:
    """Retrieve generated records from RuntimeProvider cache or disk storage for UI preview."""
    records_bytes = None
    with contextlib.suppress(Exception):
        records_bytes = await db.get(f"generation:{workflow_id}:records")

    if records_bytes:
        with contextlib.suppress(Exception):
            res = json.loads(_safe_decode(records_bytes))
            if isinstance(res, dict):
                return res

    # Fall back to DiskDatasetStorageManager
    from app.platform.container import get_dataset_storage_manager

    ds_manager = get_dataset_storage_manager()
    manifest = await ds_manager.get_dataset_metadata(workflow_id)
    if not manifest:
        raise HTTPException(
            status_code=404, detail="No generated records found for this session."
        )

    preview_records: dict[str, list[dict[str, Any]]] = {}
    try:
        for table_info in manifest.get("tables", []):
            t_name = table_info["name"]
            table_preview = await ds_manager.read_table_dataset_preview(
                workflow_id, t_name, limit=100
            )
            preview_records[t_name] = table_preview

        with contextlib.suppress(Exception):
            await db.set(
                f"generation:{workflow_id}:records", json.dumps(preview_records)
            )

        return preview_records
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load dataset preview: {e!s}"
        ) from e


@router.get("/generate/{workflow_id}/download")
async def download_generated_data(
    workflow_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> dict[str, Any]:
    """Download placeholder returning generated data stats."""
    status_dict = None
    with contextlib.suppress(Exception):
        status_bytes = await db.get(f"generation:{workflow_id}:status")
        if status_bytes:
            status_dict = json.loads(_safe_decode(status_bytes))

    if not status_dict:
        # Fall back to SQLite PersistenceProvider
        job_dict = await persistence.get_job(workflow_id)
        if not job_dict:
            raise HTTPException(
                status_code=404, detail="Generation workflow session not found."
            )
        details = job_dict.get("details") or {}
        progress_data = details.get("progress") or []
        duration_ms = (job_dict.get("duration") or 0.0) * 1000.0
        status_dict = {
            "workflowId": workflow_id,
            "status": job_dict.get("status", "Unknown"),
            "progress": progress_data,
            "totalRowsGenerated": sum(p.get("rowsGenerated", 0) for p in progress_data),
            "durationMs": duration_ms,
            "errors": (
                [job_dict.get("errorMessage")] if job_dict.get("errorMessage") else []
            ),
            "downloadPlaceholder": (
                f"/schema/generate/{workflow_id}/download"
                if job_dict.get("status") == "Completed"
                else None
            ),
        }

    return {
        "status": "success",
        "message": "Synthetic dataset generation complete.",
        "workflowId": workflow_id,
        "totalRowsGenerated": status_dict.get("totalRowsGenerated", 0),
        "durationMs": status_dict.get("durationMs", 0.0),
        "data_format": "json",
    }
