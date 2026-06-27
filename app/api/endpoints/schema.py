import json
import re
from typing import TYPE_CHECKING, Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_redis
from app.schemas.schema_design import (
    AIAssistantResponse,
    AISuggestionModel,
    SchemaModel,
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
    db: RedisType = Depends(get_redis),  # noqa: B008
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
    db: RedisType = Depends(get_redis),  # noqa: B008
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
