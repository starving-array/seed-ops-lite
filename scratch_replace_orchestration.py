import re
import json

with open("app/api/endpoints/schema/generation.py", "r", encoding="utf-8") as f:
    content = f.read()

target_block = """    try:
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

            # Write generated table records to Parquet using DiskDatasetStorageManager
            from app.platform.container import get_dataset_storage_manager

            ds_manager = get_dataset_storage_manager()
            await ds_manager.write_table_dataset(
                workflow_id, t_name, all_records.get(t_name, [])
            )"""

replacement = """    try:
        from app.seeder.allocator import RecordAllocator
        from app.seeder.relationship_allocator import RelationshipAllocator
        from app.seeder.pk_generator import PrimaryKeyGenerator
        from app.seeder.fk_injector import ForeignKeyInjector
        from app.seeder.math_computer import MathComputer
        
        # 1. Allocate Placeholders
        placeholders = RecordAllocator.allocate(ordered_tables, row_targets)
        
        # 2. Allocate Relationships
        relationship_map = RelationshipAllocator.allocate(schema, placeholders, seed)
        
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
                    if rel.sourceTableId == table_obj.id and rel.sourceColumnId == col.id:
                        is_fk = True
                        break
                    if rel.targetTableId == table_obj.id and rel.targetColumnId == col.id:
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
            # 6. Generate PKs
            PrimaryKeyGenerator.generate(schema, placeholders, seed)
            
            # 7. Inject FKs
            ForeignKeyInjector.inject(schema, placeholders, relationship_map)
            
            # 8. Compute Math
            MathComputer.compute(schema, placeholders)
            
            # 9. Assign all_records and Write Parquet
            from app.platform.container import get_dataset_storage_manager
            ds_manager = get_dataset_storage_manager()
            
            for t_name in ordered_tables:
                # Remove internal _ref_id, _table, _index
                clean_records = []
                for p in placeholders[t_name]:
                    clean_p = {k: v for k, v in p.items() if not k.startswith("_")}
                    clean_records.append(clean_p)
                    
                all_records[t_name] = clean_records
                await ds_manager.write_table_dataset(workflow_id, t_name, clean_records)"""

if target_block in content:
    content = content.replace(target_block, replacement)
    with open("app/api/endpoints/schema/generation.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Success")
else:
    print("Target block not found. Could not replace.")
