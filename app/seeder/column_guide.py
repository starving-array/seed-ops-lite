"""Column intelligence: schema fingerprint, analysis, prompt, and orchestration."""

import contextlib
import hashlib
import json
from typing import Any

COLUMN_ANALYSIS_PROMPT = """You are a database schema analyst. Analyze each column in the provided schema and output a JSON object describing the business logic for every column.

For each table and each column, determine:
1. business_meaning: What this column represents in business terms
2. depends_on: List of other column names this column's value depends on (empty list if independent)
3. formula: If the column is computed from other columns, provide the arithmetic/logical formula. If not computed, use null.
4. value_range_hint: What realistic values look like (e.g., "1-10", "CUS001-CUS999", "positive decimal", "YYYY-MM-DD date in 2025-2026")
5. constraints: List of constraints (e.g., "NOT NULL", "UNIQUE", "grand_total >= subtotal", "quantity >= 1")

Schema:
{schema_json}

Respond ONLY with the JSON object in this exact structure:
{{
  "table_name": {{
    "column_name": {{
      "business_meaning": "...",
      "depends_on": [],
      "formula": null,
      "value_range_hint": "...",
      "constraints": []
    }}
  }}
}}
"""


def compute_schema_fingerprint(schema: Any) -> str:
    """Generate a deterministic SHA-256 fingerprint for a schema.

    The fingerprint captures table names, column names, types, nullability,
    PK/FK status, and relationship structure. Any schema change produces a
    different fingerprint, triggering column intelligence regeneration.
    """
    canonical: dict[str, Any] = {"tables": [], "relationships": []}

    for table in schema.tables:
        t_info: dict[str, Any] = {
            "name": table.name,
            "columns": [
                {
                    "name": col.name,
                    "type": col.type,
                    "nullable": col.is_nullable,
                    "pk": col.is_primary_key,
                }
                for col in table.columns
            ],
        }
        canonical["tables"].append(t_info)

    for rel in schema.relationships:
        r_info: dict[str, Any] = {
            "source": rel.source_table_id,
            "source_col": rel.source_column_id,
            "target": rel.target_table_id,
            "target_col": rel.target_column_id,
            "type": rel.type,
        }
        canonical["relationships"].append(r_info)

    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _schema_to_canonical_json(schema: Any) -> str:
    """Serialize a schema to a canonical JSON string for prompt context."""
    return json.dumps(
        {
            "tables": [
                {
                    "name": t.name,
                    "columns": [
                        {
                            "name": col.name,
                            "type": col.type,
                            "nullable": col.is_nullable,
                            "pk": col.is_primary_key,
                        }
                        for col in t.columns
                    ],
                }
                for t in schema.tables
            ],
            "relationships": [
                {
                    "source_table": rel.source_table_id,
                    "source_column": rel.source_column_id,
                    "target_table": rel.target_table_id,
                    "target_column": rel.target_column_id,
                    "type": rel.type,
                }
                for rel in schema.relationships
            ],
        },
        indent=2,
    )


COLUMN_GUIDE_REDIS_PREFIX = "colguide:"
COLUMN_GUIDE_REDIS_TTL = 86400  # 1 day


async def get_column_guide(
    schema: Any,
    runtime: Any,
    persistence: Any,
) -> dict[str, Any]:
    """Retrieve column business logic for a schema.

    Resolution order:
    1. Redis cache (fingerprint key, TTL 1d)
    2. SQLite DB (persistent)
    3. LLM analysis (cache+DB miss) — stores result in both on success

    Returns a dict mapping table_name -> column_name -> business logic.
    """
    from app.llm.gateway import LLMGateway
    from app.llm.models import LLMRequest

    fingerprint = compute_schema_fingerprint(schema)
    redis_key = f"{COLUMN_GUIDE_REDIS_PREFIX}{fingerprint}"

    # 1. Check Redis
    with contextlib.suppress(Exception):
        cached = await runtime.get(redis_key)
        if cached:
            from app.api.endpoints.schema.helpers import _safe_decode

            decoded = json.loads(_safe_decode(cached))
            if isinstance(decoded, dict):
                return decoded

    # 2. Check SQLite
    with contextlib.suppress(Exception):
        db_result = await persistence.get_business_logic(fingerprint)
        if db_result:
            logic = db_result.get("business_logic", {})
            # Prime Redis
            with contextlib.suppress(Exception):
                await runtime.set(
                    redis_key, json.dumps(logic), expire=COLUMN_GUIDE_REDIS_TTL
                )
            return dict(logic) if isinstance(logic, dict) else {}

    # 3. LLM Analysis
    schema_json = _schema_to_canonical_json(schema)
    prompt_text = COLUMN_ANALYSIS_PROMPT.format(schema_json=schema_json)

    llm_request = LLMRequest(
        prompt=prompt_text,
        system_instruction="You are a database schema analyst. Output ONLY valid JSON.",
        json_mode=True,
        temperature=0.1,
    )

    gateway = LLMGateway()
    response = await gateway.generate(llm_request)

    if not response or not response.text:
        raise RuntimeError("Column analysis: LLM returned empty response.")

    try:
        result = json.loads(response.text)
    except json.JSONDecodeError as err:
        raise RuntimeError(
            f"Column analysis: LLM returned invalid JSON: {response.text[:500]}"
        ) from err

    if not isinstance(result, dict):
        raise RuntimeError(
            f"Column analysis: expected dict, got {type(result).__name__}"
        )

    # 4. Store in Redis + DB
    with contextlib.suppress(Exception):
        await runtime.set(redis_key, json.dumps(result), expire=COLUMN_GUIDE_REDIS_TTL)

    with contextlib.suppress(Exception):
        await persistence.save_business_logic(fingerprint, result)

    return result


async def invalidate_column_guide(
    schema: Any,
    runtime: Any,
    persistence: Any,
) -> None:
    """Delete cached column business logic for a schema (e.g., on schema change)."""
    fingerprint = compute_schema_fingerprint(schema)
    redis_key = f"{COLUMN_GUIDE_REDIS_PREFIX}{fingerprint}"

    with contextlib.suppress(Exception):
        await runtime.delete(redis_key)

    with contextlib.suppress(Exception):
        await persistence.delete_business_logic(fingerprint)
