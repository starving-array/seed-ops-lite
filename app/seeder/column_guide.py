"""Column intelligence: schema fingerprint, analysis, prompt, and orchestration."""

import contextlib
import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

# ── Pydantic models for column guide schema ──────────────────────────────


class ValueRange(BaseModel):
    min: float = 0
    max: float = 100
    distribution: str = "uniform"


class TemporalRule(BaseModel):
    reference_column: str = ""
    relation: str = ">="
    min_offset_days: int = 1
    max_offset_days: int = 5
    distribution: str = "exponential"


class Workflow(BaseModel):
    allowed_transitions: dict[str, list[str]] = Field(default_factory=dict)
    terminal_states: list[str] = Field(default_factory=list)


class ColumnGuideEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    business_meaning: str = ""
    data_type: str = "string"
    is_computed: bool = False
    formula: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    depends_on_parent: str | None = None
    value_range: ValueRange | None = None
    categorical_weights: dict[str, float] | None = None
    temporal_rule: TemporalRule | None = None
    workflow: Workflow | None = None
    constraints: list[str] = Field(default_factory=list)


class ColumnGuideResult(RootModel[dict[str, dict[str, ColumnGuideEntry]]]):
    root: dict[str, dict[str, ColumnGuideEntry]]


COLUMN_ANALYSIS_PROMPT = """\
You are an Expert Enterprise Data Architect, Domain Modeling Specialist, and Synthetic Data Engineer.

Your task is to analyze an arbitrary database schema and produce a reusable Business Semantic Schema suitable for realistic synthetic data generation.

The input schema may belong to any business domain, including but not limited to:
* E-commerce, ERP, Banking, FinTech, Insurance, Healthcare, Logistics
* Manufacturing, Telecom, HRMS, CRM, SaaS, Education, Government
* Gaming, IoT, Social Media, Custom Enterprise Systems

Your responsibility is to understand the business intent behind the schema and infer realistic business behavior, validations, calculations, workflows, dependencies, and distributions.

Do NOT generate synthetic data.

---

# KEY COLUMN EXCLUSION RULE (APPLIES TO THE ENTIRE OUTPUT)

Primary keys and foreign keys are structural/relational concerns, handled entirely by a separate relationship engine. They carry no business semantics of their own and must be treated as invisible to this analysis.

A column is a "key column" and must be EXCLUDED if any of the following is true:
* It is declared PRIMARY KEY (single or composite).
* It is declared with a REFERENCES / FOREIGN KEY constraint.
* It is a surrogate identifier whose sole purpose is linking rows (e.g. *_id, *_uuid, *_key columns that are PK or FK by declaration).

For every excluded key column:
* Do NOT include it in the JSON output for any table.
* You MAY silently use key columns to understand which tables relate to which (for reasoning purposes only), but this understanding must never surface as a column entry.

---

# ANALYSIS STEPS

For each table and column, perform the following analysis silently (do not output these steps — only output the final JSON):

## Step 1: Table Understanding
Determine: business purpose, real-world meaning, business domain context, table category (Master, Transaction, Reference, Dimension, Fact, Event, Audit, History, Snapshot, Configuration, Workflow, Inventory, Ledger, Document, Metadata, Lookup, or Unknown), confidence level.

## Step 2: Column Semantic Understanding
For every NON-KEY column determine: business meaning, real-world meaning, human interpretation, business importance, whether user-entered or system-generated. Classify into: Business Code, Financial, Quantity, Percentage, Status, Date, Measurement, Boolean Flag, Enumeration, Metadata, Audit, Computed, Text Description, or Reference Code.

## Step 3: Validation Rule Discovery
Infer realistic validations for non-key business fields: range validations, regex validations, domain validations, date validations, cross-column validations, temporal validations, state validations, financial validations. Do not produce validations about key uniqueness or referential integrity.

## Step 4: Derived Field Discovery
Detect non-key fields that should be calculated rather than generated. Examples: line_total = quantity * unit_price, subtotal = SUM(line_total), tax_amount = subtotal * tax_rate, grand_total = subtotal + tax + shipping - discount. Provide the formula and list of dependent column names.

## Step 5: Business Dependency Discovery
Identify intra-row and cross-table dependencies between business values, never between key columns. Examples: grand_total depends on subtotal/tax/shipping/discount, discount <= subtotal, delivery_date >= shipped_date >= order_date. Infer dependencies even if not explicitly represented in constraints.

## Step 6: Distribution Modeling
For every non-key business attribute infer: realistic minimum, maximum, average values, expected skew, distribution shape (Uniform, Normal, Log Normal, Exponential, Power Law, Seasonal, Weighted Categories, Zipf Distribution).

## Step 7: Workflow Discovery
For status/state-type business columns: valid transitions, invalid transitions, terminal states, retry states, rollback states. Identify business process flows (e.g., PENDING -> PROCESSING -> APPROVED -> COMPLETED).

## Step 8: Temporal Behavior Discovery
For date/timestamp business columns: business delays, processing times, waiting periods, SLA windows, expected durations. Examples: order_date -> shipped_date averages 1-3 days, shipped_date -> delivered_date averages 2-5 days.

## Step 9: Business Invariants
Rules that should never be violated, expressed in terms of business values only. Examples: grand_total cannot be negative, tax cannot exceed subtotal, quantity cannot be zero, delivery_date cannot occur before order_date, completed records cannot return to draft state.

## Step 10: Confidence Scoring
For every inference: source (explicit_schema, business_inference, heuristic, assumption) and confidence (HIGH, MEDIUM, LOW). Clearly distinguish explicit schema facts from inferred business logic from assumptions.

---

Schema:
{schema_json}

---

# CRITICAL: OUTPUT FORMAT — YOU MUST FOLLOW THIS EXACTLY

Respond ONLY with a JSON object in this EXACT structure — a dictionary of dictionaries:

{{
  "table_name": {{
    "column_name": {{
      "business_meaning": "What this column represents in business terms",
      "data_type": "string|int|decimal|date|boolean",
      "is_computed": false,
      "formula": null,
      "depends_on": [],
      "depends_on_parent": null,
      "value_range": {{"min": 0, "max": 100, "distribution": "uniform"}},
      "categorical_weights": null,
      "temporal_rule": null,
      "workflow": null,
      "constraints": []
    }}
  }}
}}

This is NOT a list. It is NOT {{"tables": [...]}}. It is a flat dictionary where:
* Each KEY is a table name (string)
* Each VALUE is a dictionary where:
  * Each KEY is a column name (string)
  * Each VALUE is an object with the fields below

Field Descriptions:
* "business_meaning": Concise business meaning of the column.
* "data_type": One of "string", "int", "decimal", "date", "boolean".
* "is_computed": true if this column is derived from other columns (formula required).
* "formula": Arithmetic/expression formula if is_computed is true (e.g. "quantity * unit_price", "subtotal + tax + shipping_fee - discount"). Use null if not computed.
* "depends_on": List of column names this value depends on (empty if independent).
* "depends_on_parent": If this column's value depends on a parent table's column, specify "parent_table.column_name" (e.g. "customers.created_at"). null if not cross-table dependent.
* "value_range": {{"min": N, "max": N, "distribution": "uniform|normal|log_normal|exponential|power_law|weighted_categories"}}. Use null if not numeric or not applicable. For categorical/status columns, use categorical_weights instead.
* "categorical_weights": For categorical/status/enum columns, a dict of value -> weight (weights should sum to 1.0). Example: {{"ACTIVE": 0.7, "INACTIVE": 0.2, "SUSPENDED": 0.1}}. null if not categorical.
* "temporal_rule": For date/timestamp columns that depend on another date column: {{"reference_column": "other_date_col", "relation": ">=", "min_offset_days": 1, "max_offset_days": 5, "distribution": "exponential"}}. null if not temporally dependent.
* "workflow": For status/state columns: {{"allowed_transitions": {{"PENDING": ["PROCESSING", "CANCELLED"]}}, "terminal_states": ["COMPLETED", "CANCELLED"]}}. null if not a workflow state.
* "constraints": List of business constraint expressions (e.g. "quantity > 0", "delivery_date >= shipped_date", "discount <= subtotal").

Rules:
* Include ONLY NON-KEY columns. No PK/FK columns anywhere.
* Every column entry MUST include ALL fields listed above. Use null for optional fields that don't apply.
* Do NOT include raw "value_range_hint" strings — always use the structured value_range object when applicable.
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


def _normalize_column_guide(result: dict[str, Any]) -> dict[str, Any]:
    """Normalize LLM output to {table_name: {column_name: {info}}} format.

    Handles both flat dict format and list format {"tables": [...]}.
    Validates every entry against ColumnGuideEntry and fills safe defaults.
    """
    normalized: dict[str, Any] = {}

    # Try flat dict format: {table: {col: {...}}}
    if all(isinstance(v, dict) for v in result.values()):
        first_val: dict[str, Any] = next(iter(result.values()), {})
        if all(isinstance(v, dict) for v in first_val.values()):
            normalized = result

    # Try list format: {"tables": [{"name": T, "columns": [...]}]}
    if not normalized:
        tables_list = result.get("tables")
        if isinstance(tables_list, list):
            for table_entry in tables_list:
                t_name = table_entry.get("name")
                columns = table_entry.get("columns", [])
                if not t_name or not isinstance(columns, list):
                    continue
                col_map: dict[str, Any] = {}
                for col_entry in columns:
                    col_name = col_entry.get("name")
                    if not col_name:
                        continue
                    col_map[col_name] = {
                        k: col_entry.get(k) for k in ColumnGuideEntry.model_fields
                    }
                normalized[t_name] = col_map

    if not normalized:
        return result

    # Validate each entry against ColumnGuideEntry, filling safe defaults
    validated: dict[str, dict[str, Any]] = {}
    for t_name, col_dict in normalized.items():
        if not isinstance(col_dict, dict):
            continue
        v_cols: dict[str, Any] = {}
        for col_name, col_info in col_dict.items():
            if not isinstance(col_info, dict):
                col_info = {}  # noqa: PLW2901
            try:
                entry = ColumnGuideEntry(**col_info)
                v_cols[col_name] = entry.model_dump(exclude_defaults=False)
            except Exception:
                v_cols[col_name] = ColumnGuideEntry(
                    business_meaning=str(col_info.get("business_meaning", ""))
                ).model_dump(exclude_defaults=False)
        validated[t_name] = v_cols

    return validated


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

    # 3. LLM Analysis (routed through AIContractNormalizer for retry/validation)
    from app.llm.contracts.normalizer import AIContractNormalizer
    from app.llm.contracts.request import AIContractRequest

    schema_json = _schema_to_canonical_json(schema)
    prompt_text = COLUMN_ANALYSIS_PROMPT.format(schema_json=schema_json)

    llm_request = LLMRequest(
        prompt=prompt_text,
        system_instruction="You are an expert database architect. Output ONLY valid JSON matching the required structure exactly.",
        json_mode=True,
        temperature=0.1,
        max_tokens=8192,
    )

    contract_request = AIContractRequest[ColumnGuideResult](
        prompt=llm_request,
        response_schema=ColumnGuideResult,
        json_mode=True,
    )

    gateway = LLMGateway()
    contract_response = await AIContractNormalizer.execute_contract(
        gateway, contract_request
    )

    if not contract_response.success or contract_response.data is None:
        err_msg = "Unknown error"
        if contract_response.error:
            err_msg = contract_response.error.message
        raise RuntimeError(f"Column analysis failed: {err_msg}")

    # Extract validated data — ColumnGuideResult is a RootModel, data.root is the dict
    result = _normalize_column_guide(contract_response.data.model_dump())

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
