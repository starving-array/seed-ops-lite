import json
import re
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from app.api.deps import get_redis
from app.schemas.schema_design import (
    AIAssistantResponse,
    AISuggestionModel,
    ExportSettingsModel,
    GenerateRequestModel,
    GenerateResponseModel,
    JobModel,
    SchemaModel,
    TableProgressModel,
    ValidationResultModel,
)

if TYPE_CHECKING:
    RedisType = aioredis.Redis[Any]
else:
    RedisType = aioredis.Redis

router = APIRouter()

REDIS_KEY = "schema_designer:state"

RESERVED_KEYWORDS = {
    "select",
    "table",
    "order",
    "group",
    "user",
    "where",
    "join",
    "create",
    "delete",
    "update",
    "insert",
    "from",
    "into",
    "by",
    "index",
    "primary",
    "key",
    "foreign",
    "constraint",
    "null",
}
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _safe_decode(value: Any) -> str:
    """Safely decode bytes to string, or return string directly."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, str):
        return value
    return str(value)


DEFAULT_SCHEMA: dict[str, Any] = {
    "tables": [
        {
            "id": "1",
            "name": "users",
            "columns": [
                {
                    "id": "c1",
                    "name": "id",
                    "type": "INTEGER",
                    "isPrimaryKey": True,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "c2",
                    "name": "email",
                    "type": "VARCHAR",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "c3",
                    "name": "created_at",
                    "type": "TIMESTAMP",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "CURRENT_TIMESTAMP",
                },
            ],
        },
        {
            "id": "2",
            "name": "orders",
            "columns": [
                {
                    "id": "o1",
                    "name": "id",
                    "type": "INTEGER",
                    "isPrimaryKey": True,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "o2",
                    "name": "user_id",
                    "type": "INTEGER",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "",
                },
                {
                    "id": "o3",
                    "name": "total",
                    "type": "FLOAT",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "0.00",
                },
                {
                    "id": "o4",
                    "name": "status",
                    "type": "VARCHAR",
                    "isPrimaryKey": False,
                    "isNullable": False,
                    "defaultValue": "'pending'",
                },
            ],
        },
    ],
    "relationships": [
        {
            "id": "r1",
            "name": "fk_orders_user_id",
            "sourceTableId": "2",
            "sourceColumnId": "o2",
            "targetTableId": "1",
            "targetColumnId": "c1",
            "type": "many-to-one",
            "isRequired": True,
            "cascadeDelete": True,
            "cascadeUpdate": True,
        }
    ],
}


@router.get("", response_model=SchemaModel)
async def load_schema(
    db: RedisType = Depends(get_redis),
) -> SchemaModel:
    """Loads the currently saved schema state from Redis."""
    try:
        raw_state = await db.get(REDIS_KEY)
        if not raw_state:
            return SchemaModel(**DEFAULT_SCHEMA)
        return SchemaModel(**json.loads(raw_state))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load schema: {exc}",
        ) from exc


@router.post("", status_code=status.HTTP_200_OK)
async def save_schema(
    schema: SchemaModel,
    db: RedisType = Depends(get_redis),
) -> dict[str, str]:
    """Saves the current schema state to Redis."""
    try:
        serialized = json.dumps(schema.model_dump(by_alias=True))
        await db.set(REDIS_KEY, serialized)
        return {"status": "success", "message": "Schema saved successfully"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save schema: {exc}",
        ) from exc


@router.post("/validate", response_model=list[ValidationResultModel])
async def validate_schema(schema: SchemaModel) -> list[ValidationResultModel]:
    """Validates the schema design on the backend using the validation engine rules."""
    results: list[ValidationResultModel] = []
    tables = schema.tables
    relationships = schema.relationships

    # Check Table rules
    table_names: set[str] = set()
    for t in tables:
        if not t.name or t.name.strip() == "":
            results.append(
                ValidationResultModel(
                    id=f"table-empty-{t.id}",
                    category="Tables",
                    severity="Error",
                    title="Empty Table Name",
                    description="A table is defined with an empty or whitespace name.",
                    suggestedFix="Rename the table with a valid unique name.",
                )
            )
        else:
            if t.name.lower() in table_names:
                results.append(
                    ValidationResultModel(
                        id=f"table-dup-{t.id}",
                        category="Tables",
                        severity="Error",
                        title=f'Duplicate Table Name: "{t.name}"',
                        description=f'Multiple tables are defined with the name "{t.name}". Table names must be unique.',
                        suggestedFix="Rename this table to avoid naming conflicts.",
                    )
                )
            table_names.add(t.name.lower())

            if not IDENTIFIER_REGEX.match(t.name):
                results.append(
                    ValidationResultModel(
                        id=f"table-naming-invalid-{t.id}",
                        category="Naming",
                        severity="Error",
                        title=f'Invalid Table Identifier: "{t.name}"',
                        description=f'The table name "{t.name}" contains invalid characters. Database table identifiers should only contain letters, numbers, and underscores, and must start with a letter or underscore.',
                        suggestedFix="Rename the table using snake_case conventions.",
                    )
                )

            if t.name.lower() in RESERVED_KEYWORDS:
                results.append(
                    ValidationResultModel(
                        id=f"table-naming-keyword-{t.id}",
                        category="Naming",
                        severity="Warning",
                        title=f'Reserved SQL Keyword used: "{t.name}"',
                        description=f'The table name "{t.name}" is a reserved SQL keyword. Using reserved keywords can cause syntactical issues during query compiler executions.',
                        suggestedFix=f'Consider renaming the table (e.g. prefixing or suffixing it, like "app_{t.name}").',
                    )
                )

            if any(char.isupper() for char in t.name):
                results.append(
                    ValidationResultModel(
                        id=f"table-naming-case-{t.id}",
                        category="Naming",
                        severity="Warning",
                        title=f'Non-standard Case: "{t.name}"',
                        description=f'The table name "{t.name}" contains uppercase letters. Database best practices recommend lowercase snake_case formatting.',
                        suggestedFix=f'Rename the table to lowercase snake_case (e.g., "{t.name.lower()}").',
                    )
                )

        if len(t.columns) == 0:
            results.append(
                ValidationResultModel(
                    id=f"table-empty-cols-{t.id}",
                    category="Tables",
                    severity="Error",
                    title=f'Table "{t.name}" has no columns',
                    description="A table must contain at least one column definition to generate SQL inserts.",
                    suggestedFix="Navigate back to the Schema Designer and add at least one column (e.g., a primary key).",
                )
            )

        # Check Column rules
        col_names: set[str] = set()
        pk_count = 0
        for c in t.columns:
            if not c.name or c.name.strip() == "":
                results.append(
                    ValidationResultModel(
                        id=f"col-empty-{t.id}-{c.id}",
                        category="Columns",
                        severity="Error",
                        title=f'Empty Column Name in Table "{t.name}"',
                        description="A column in this table is defined with an empty or whitespace name.",
                        suggestedFix="Specify a valid column name.",
                    )
                )
            else:
                if c.name.lower() in col_names:
                    results.append(
                        ValidationResultModel(
                            id=f"col-dup-{t.id}-{c.id}",
                            category="Columns",
                            severity="Error",
                            title=f'Duplicate Column Name: "{c.name}" in Table "{t.name}"',
                            description=f'Table "{t.name}" has multiple columns named "{c.name}". Column names must be unique within a table.',
                            suggestedFix="Rename the column to avoid conflicts.",
                        )
                    )
                col_names.add(c.name.lower())

                if not IDENTIFIER_REGEX.match(c.name):
                    results.append(
                        ValidationResultModel(
                            id=f"col-naming-invalid-{t.id}-{c.id}",
                            category="Naming",
                            severity="Error",
                            title=f'Invalid Column Identifier: "{c.name}" in Table "{t.name}"',
                            description=f'The column name "{c.name}" in table "{t.name}" contains invalid characters. Column identifiers must be alphanumeric or underscores.',
                            suggestedFix="Rename the column to use only alphanumeric characters and underscores.",
                        )
                    )

                if c.name.lower() in RESERVED_KEYWORDS:
                    results.append(
                        ValidationResultModel(
                            id=f"col-naming-keyword-{t.id}-{c.id}",
                            category="Naming",
                            severity="Warning",
                            title=f'Reserved SQL Keyword in Column: "{c.name}" in Table "{t.name}"',
                            description=f'Column "{c.name}" in table "{t.name}" is a reserved SQL keyword. This might cause compilation warnings on database servers.',
                            suggestedFix='Consider using a more descriptive column name (e.g. "order_date" instead of "date").',
                        )
                    )

                if any(char.isupper() for char in c.name):
                    results.append(
                        ValidationResultModel(
                            id=f"col-naming-case-{t.id}-{c.id}",
                            category="Naming",
                            severity="Warning",
                            title=f'Non-standard Case: "{c.name}" in Table "{t.name}"',
                            description=f'The column name "{c.name}" in table "{t.name}" contains uppercase letters. Lowercase snake_case is highly recommended.',
                            suggestedFix=f'Rename the column to lowercase snake_case (e.g., "{c.name.lower()}").',
                        )
                    )

            if not c.type:
                results.append(
                    ValidationResultModel(
                        id=f"col-type-missing-{t.id}-{c.id}",
                        category="Data Types",
                        severity="Error",
                        title=f'Missing Data Type for Column "{c.name}" in Table "{t.name}"',
                        description="Every column definition must carry an explicit SQL type binding.",
                        suggestedFix="Select a valid type (e.g., VARCHAR, INTEGER, TEXT, etc.) from the types dropdown.",
                    )
                )

            if c.is_primary_key:
                pk_count += 1

        if pk_count > 1:
            results.append(
                ValidationResultModel(
                    id=f"table-multiple-pk-{t.id}",
                    category="Constraints",
                    severity="Error",
                    title=f'Multiple Primary Keys in Table "{t.name}"',
                    description=f'Table "{t.name}" has {pk_count} columns configured as Primary Keys. Most relational databases only support a single primary key per table.',
                    suggestedFix="Toggle off primary key settings for duplicate columns, or build a composite constraint.",
                )
            )

    # Check Relationship rules
    rel_keys: set[str] = set()
    for r in relationships:
        s_table = next((t for t in tables if t.id == r.source_table_id), None)
        t_table = next((t for t in tables if t.id == r.target_table_id), None)

        if not r.source_table_id or not s_table:
            results.append(
                ValidationResultModel(
                    id=f"rel-source-table-missing-{r.id}",
                    category="Relationships",
                    severity="Error",
                    title=f'Missing Source Table in Relationship "{r.name}"',
                    description="The configured source table reference cannot be found in the current schema design.",
                    suggestedFix="Re-assign or delete this relationship.",
                )
            )

        if not r.target_table_id or not t_table:
            results.append(
                ValidationResultModel(
                    id=f"rel-target-table-missing-{r.id}",
                    category="Relationships",
                    severity="Error",
                    title=f'Missing Target Table in Relationship "{r.name}"',
                    description="The configured target table reference cannot be found in the current schema design.",
                    suggestedFix="Re-assign or delete this relationship.",
                )
            )

        if s_table:
            s_col = next(
                (c for c in s_table.columns if c.id == r.source_column_id), None
            )
            if not r.source_column_id or not s_col:
                results.append(
                    ValidationResultModel(
                        id=f"rel-source-col-missing-{r.id}",
                        category="Relationships",
                        severity="Error",
                        title=f'Missing Source Column in Relationship "{r.name}"',
                        description=f'The referenced source column does not exist in table "{s_table.name}".',
                        suggestedFix="Select a valid source column.",
                    )
                )

        if t_table:
            t_col = next(
                (c for c in t_table.columns if c.id == r.target_column_id), None
            )
            if not r.target_column_id or not t_col:
                results.append(
                    ValidationResultModel(
                        id=f"rel-target-col-missing-{r.id}",
                        category="Relationships",
                        severity="Error",
                        title=f'Missing Target Column in Relationship "{r.name}"',
                        description=f'The referenced target column does not exist in table "{t_table.name}".',
                        suggestedFix="Select a valid target column.",
                    )
                )

        if (
            r.source_table_id
            and r.target_table_id
            and r.source_table_id == r.target_table_id
        ):
            results.append(
                ValidationResultModel(
                    id=f"rel-self-ref-{r.id}",
                    category="Relationships",
                    severity="Warning",
                    title=f'Self-referencing Relationship: "{r.name}"',
                    description=f'Table "{s_table.name if s_table else "unknown"}" is configured to reference itself. This creates recursive hierarchies.',
                    suggestedFix="Verify this self-reference (like manager_id -> user_id) is intentional.",
                )
            )

        rel_key = f"{r.source_table_id}-{r.source_column_id}-{r.target_table_id}-{r.target_column_id}"
        if rel_key in rel_keys:
            results.append(
                ValidationResultModel(
                    id=f"rel-dup-{r.id}",
                    category="Relationships",
                    severity="Error",
                    title=f'Duplicate Relationship Definition: "{r.name}"',
                    description="Multiple relationships configure the exact same foreign key link points.",
                    suggestedFix="Delete the duplicate relationship definition.",
                )
            )
        rel_keys.add(rel_key)

    # If no warnings or errors, return success items
    if len(results) == 0 and len(tables) > 0:
        categories = [
            "Tables",
            "Columns",
            "Relationships",
            "Naming",
            "Constraints",
            "Data Types",
        ]
        for cat in categories:
            results.append(
                ValidationResultModel(
                    id=f"pass-{cat}",
                    category=cat,
                    severity="Passed",
                    title=f"{cat} Checks Passed",
                    description=f"All validation checks in the {cat} category compiled successfully.",
                    suggestedFix="No fix required.",
                )
            )

    return results


def generate_ddl_from_schema(schema: SchemaModel) -> str:
    ddl_parts = []
    table_map = {t.id: t for t in schema.tables}

    for table in schema.tables:
        lines = []
        lines.append(f"CREATE TABLE {table.name} (")

        column_definitions = []
        for col in table.columns:
            col_def = f"    {col.name} {col.type}"
            if col.is_primary_key:
                col_def += " PRIMARY KEY"
            if not col.is_nullable:
                col_def += " NOT NULL"
            if col.default_value and col.default_value.strip():
                col_def += f" DEFAULT {col.default_value.strip()}"
            column_definitions.append(col_def)

        # Add foreign key constraints
        for rel in schema.relationships:
            if rel.source_table_id == table.id:
                source_col = next(
                    (c for c in table.columns if c.id == rel.source_column_id),
                    None,
                )
                target_table = table_map.get(rel.target_table_id)
                if target_table:
                    target_col = next(
                        (
                            c
                            for c in target_table.columns
                            if c.id == rel.target_column_id
                        ),
                        None,
                    )
                    if source_col and target_col:
                        fk_line = f"    FOREIGN KEY ({source_col.name}) REFERENCES {target_table.name}({target_col.name})"
                        column_definitions.append(fk_line)

        lines.append(",\n".join(column_definitions))
        lines.append(");")
        ddl_parts.append("\n".join(lines))

    return "\n\n".join(ddl_parts)


@router.post("/ai-assist", response_model=AIAssistantResponse)
async def ai_schema_assistant(schema: SchemaModel) -> AIAssistantResponse:
    """Analyzes current schema design using SchemaValidationAgent and returns suggestions."""
    import hashlib
    import time

    from app.agents.schema_validation.agent import SchemaValidationAgent

    start_time = time.perf_counter()

    if not schema.tables:
        return AIAssistantResponse(
            status="Completed",
            summary="No tables configured in the schema. Please add tables to begin design analysis.",
            suggestions=[],
            executionDurationMs=0.0,
        )

    try:
        ddl = generate_ddl_from_schema(schema)
        agent = SchemaValidationAgent()
        report = await agent.validate_schema(ddl)

        suggestions = []
        for finding in report.findings:
            # Map category
            orig_cat = finding.category.lower().strip()
            category = "Best Practices"
            if orig_cat == "naming":
                category = "Naming"
            elif orig_cat == "relationships":
                category = "Relationships"
            elif orig_cat in ("structure", "data_quality"):
                category = "Validation"
            elif orig_cat == "best_practices":
                desc_lower = finding.description.lower()
                sug_lower = (finding.suggestion or "").lower()
                perf_keywords = [
                    "index",
                    "performance",
                    "query",
                    "cache",
                    "slow",
                    "speed",
                    "optimize",
                    "tuning",
                    "scalability",
                ]
                if any(kw in desc_lower or kw in sug_lower for kw in perf_keywords):
                    category = "Performance"
                else:
                    category = "Best Practices"

            # Derive Title and Explanation
            description = finding.description
            title = f"{category} Recommendation"
            explanation = description

            # Look for common patterns with colons or dashes
            for sep in (":", " - "):
                if sep in description:
                    parts = description.split(sep, 1)
                    candidate = parts[0].strip()
                    if len(candidate) < 60:
                        title = candidate
                        explanation = parts[1].strip()
                        break

            # If title wasn't found or is too generic, summarize description to first sentence
            if title == f"{category} Recommendation":
                first_sentence = description.split(".")[0].strip()
                if len(first_sentence) < 60:
                    title = first_sentence
                else:
                    title = first_sentence[:57] + "..."

            # Generate a stable ID based on category, title, explanation, suggestion
            payload = f"{category}:{title}:{explanation}:{finding.suggestion or ''}"
            suggestion_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

            suggestions.append(
                AISuggestionModel(
                    id=suggestion_id,
                    category=category,
                    severity=finding.severity.lower(),
                    title=title,
                    explanation=explanation,
                    suggestedAction=finding.suggestion,
                )
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return AIAssistantResponse(
            status="Completed",
            summary=report.summary,
            suggestions=suggestions,
            executionDurationMs=round(duration_ms, 2),
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return AIAssistantResponse(
            status="Failed",
            summary=f"AI Schema Assistant is currently unavailable: {exc}",
            suggestions=[],
            executionDurationMs=round(duration_ms, 2),
        )


async def update_job(
    db_client: RedisType,
    job_id: str,
    job_type: str = "generation",
    status: str = "Queued",
    progress: float = 0.0,
    started_at: str | None = None,
    finished_at: str | None = None,
    duration: float = 0.0,
    result_summary: str | None = None,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    import json
    from datetime import datetime

    job_key = f"jobs:{job_id}"
    existing_bytes = await db_client.get(job_key)
    if existing_bytes:
        job_dict = json.loads(_safe_decode(existing_bytes))
    else:
        job_dict = {
            "jobId": job_id,
            "type": job_type,
            "status": status,
            "startedAt": started_at or datetime.utcnow().isoformat() + "Z",
            "finishedAt": None,
            "duration": 0.0,
            "progress": 0.0,
            "owner": None,
            "resultSummary": None,
            "errorMessage": None,
            "details": {},
        }
        await db_client.sadd("jobs:all_ids", job_id)

    job_dict["status"] = status
    job_dict["progress"] = round(progress, 2)
    job_dict["duration"] = round(duration, 2)

    if finished_at:
        job_dict["finishedAt"] = finished_at
    if result_summary is not None:
        job_dict["resultSummary"] = result_summary
    if error_message is not None:
        job_dict["errorMessage"] = error_message
    if details is not None:
        job_dict["details"] = details

    await db_client.set(job_key, json.dumps(job_dict))


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
    import json
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
    import json

    status_bytes = await db.get(f"generation:{workflow_id}:status")
    if not status_bytes:
        raise HTTPException(
            status_code=404, detail="Generation workflow session not found."
        )

    status_dict = json.loads(_safe_decode(status_bytes))

    # Dynamically update duration_ms if it's still running
    if status_dict.get("status") == "Running" and "startTime" in status_dict:
        import time

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
    import json

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

    import json

    status_dict = json.loads(_safe_decode(status_bytes))
    return {
        "status": "success",
        "message": "Synthetic dataset generation complete.",
        "workflowId": workflow_id,
        "totalRowsGenerated": status_dict.get("totalRowsGenerated", 0),
        "durationMs": status_dict.get("durationMs", 0.0),
        "data_format": "json",
    }


@router.get("/jobs", response_model=list[JobModel])
async def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    search: str | None = None,
    db: RedisType = Depends(get_redis),
) -> list[JobModel]:
    """Lists all historical and active background jobs, optionally applying filters."""
    import json

    job_ids_bytes = await db.smembers("jobs:all_ids")
    job_ids = [_safe_decode(j) for j in job_ids_bytes] if job_ids_bytes else []

    jobs = []
    for j_id in job_ids:
        job_bytes = await db.get(f"jobs:{j_id}")
        if job_bytes:
            job_dict = json.loads(_safe_decode(job_bytes))

            # Apply filters
            if status and job_dict.get("status", "").lower() != status.lower():
                continue
            if job_type and job_dict.get("type", "").lower() != job_type.lower():
                continue
            if search:
                search_lower = search.lower()
                id_match = search_lower in job_dict.get("jobId", "").lower()
                type_match = search_lower in job_dict.get("type", "").lower()
                if not (id_match or type_match):
                    continue

            jobs.append(JobModel(**job_dict))

    # Sort jobs by startedAt descending
    jobs.sort(key=lambda x: x.started_at, reverse=True)
    return jobs


@router.get("/jobs/{job_id}", response_model=JobModel)
async def get_job_details(
    job_id: str,
    db: RedisType = Depends(get_redis),
) -> JobModel:
    """Retrieves full details of a specific operation job."""
    import json

    job_bytes = await db.get(f"jobs:{job_id}")
    if not job_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job session {job_id} not found.",
        )

    job_dict = json.loads(_safe_decode(job_bytes))
    return JobModel(**job_dict)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_from_history(
    job_id: str,
    db: RedisType = Depends(get_redis),
) -> dict[str, str]:
    """Cancels a running job directly from the history view."""
    return await cancel_generation(workflow_id=job_id, db=db)


async def run_export_background(
    export_job_id: str,
    settings: ExportSettingsModel,
    db_client: RedisType,
) -> None:
    import io
    import json
    import time
    import zipfile
    from datetime import datetime

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
            f"generation:{settings.workflow_id}:records"
        )
        if not records_bytes:
            raise Exception(
                f"No generated dataset records found for session {settings.workflow_id}"
            )

        all_records = json.loads(_safe_decode(records_bytes))

        # Filter tables to export if specified
        if settings.tables:
            records = {t: all_records[t] for t in settings.tables if t in all_records}
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
        fmt = settings.format.lower()

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
        zip_placeholder = settings.compression

        final_filename = f"dataset_{export_job_id[:8]}"
        if settings.file_name_convention == "timestamp":
            final_filename = f"export_{int(time.time())}"

        if zip_placeholder or len(serialized_data) > 1:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                if settings.include_metadata:
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

        # 3. Store result in Redis
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
    import json

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
    import json
    import uuid
    from datetime import datetime

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
    import json

    from fastapi.responses import Response

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
