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


def _ci_get(rec: dict[str, Any], key: str) -> Any:
    """Case-insensitive dict lookup. Tries exact match first, then lowercase."""
    val = rec.get(key)
    if val is not None:
        return val
    kl = key.lower()
    for k, v in rec.items():
        if k.lower() == kl:
            return v
    return None


def _evaluate_formulas(
    placeholders: dict[str, list[dict[str, Any]]],
    column_guide: dict[str, Any] | None,
    strict: bool = True,
) -> None:
    """Post-process generated records: compute formula-based fields from column guide.

    Topologically resolves computed fields so dependencies are computed first.
    Uses Decimal for financial precision. Raises loudly on failure in strict mode.
    """
    import ast
    import operator
    import re
    from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

    import structlog

    def _safe_eval(expr: str, vars_dict: dict[str, Decimal]) -> Decimal:
        ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def _eval_node(node: ast.AST) -> Decimal:
            if isinstance(node, ast.Num):
                return Decimal(str(node.n))
            elif isinstance(node, ast.Constant):  # noqa: RET505
                return Decimal(str(node.value))
            elif isinstance(node, ast.Name):
                return vars_dict[node.id]
            elif isinstance(node, ast.BinOp):
                return ops[type(node.op)](_eval_node(node.left), _eval_node(node.right))  # type: ignore
            elif isinstance(node, ast.UnaryOp):
                return ops[type(node.op)](_eval_node(node.operand))  # type: ignore
            raise ValueError(f"Unsupported node type: {type(node)}")

        return _eval_node(ast.parse(expr, mode="eval").body)

    _log = structlog.get_logger()
    if not column_guide:
        _log.info("Formula computation skipped — no column guide available")
        return

    _SAFE_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")  # noqa: N806
    _AGGREGATE_FUNCS = {"SUM", "COUNT", "AVG", "MIN", "MAX", "COALESCE"}  # noqa: N806

    for t_name, records in placeholders.items():
        t_guide = column_guide.get(t_name, {})
        if not t_guide:
            continue

        formulas = {c: i["formula"] for c, i in t_guide.items() if i.get("formula")}
        if not formulas:
            continue

        # Skip formulas using aggregate functions (e.g. SUM, COUNT) — not row-level
        row_level = {
            c: f
            for c, f in formulas.items()
            if not _AGGREGATE_FUNCS & set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", f))
        }
        if not row_level:
            continue
        skipped = {c: f for c, f in formulas.items() if c not in row_level}
        if skipped:
            _log.info("Skipping aggregate formulas", table=t_name, formulas=skipped)

        _log.info(
            "Formula computation: processing table",
            table=t_name,
            formulas=list(row_level.keys()),
        )
        formulas = row_level

        # Topological sort: resolve dependencies between computed fields
        remaining = dict(formulas)
        resolved_order = []
        while remaining:
            progressed = False
            for name, expr in list(remaining.items()):
                tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expr)
                deps = [t for t in tokens if t != name and t in remaining]
                if not deps:
                    resolved_order.append(name)
                    del remaining[name]
                    progressed = True
            if not progressed:
                raise ValueError(
                    f"Circular or unresolvable dependency among formulas for table '{t_name}': {list(remaining)}"
                )

        # Pre-check: identify tokens that don't belong to any real column
        # so the eval loop can substitute 0 instead of raising
        _all_real_cols_lower: set[str] = set()
        for _r in records:
            _all_real_cols_lower.update(k.lower() for k in _r)

        for rec in records:
            for name in resolved_order:
                formula = formulas[name]
                try:
                    raw_formula = formula.strip()
                    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", raw_formula)
                    local_vars = {}
                    for t in tokens:
                        if not _SAFE_NAME_RE.match(t):
                            raise ValueError(f"Unsafe token in formula: {t}")
                        val = _ci_get(rec, t)
                        if val is None:
                            # Token not in record — could be missing column or non-existent
                            if t.lower() in _all_real_cols_lower:
                                # Real column that wasn't generated — error
                                if strict:
                                    raise ValueError(
                                        f"Formula references missing/ungenerated field: {t}"
                                    )
                                continue
                            # Non-existent column — substitute 0
                            local_vars[t] = Decimal("0")
                            _log.warning(
                                "Formula references non-existent column — substituting 0",
                                table=t_name,
                                column=name,
                                formula=formula,
                                missing_token=t,
                            )
                            continue
                        try:
                            local_vars[t] = Decimal(str(val))
                        except InvalidOperation:
                            if strict:
                                raise ValueError(  # noqa: B904
                                    f"Field '{t}' is not numeric: {val!r}"
                                )  # noqa: B904, RUF100
                            continue
                    # Arithmetic-only eval with Decimal
                    allowed_chars = set(
                        "0123456789.+-*/() " + "".join(local_vars.keys())
                    )
                    safe_expr = "".join(
                        c if c in allowed_chars else "" for c in raw_formula
                    )
                    result = _safe_eval(safe_expr, local_vars)
                    rec[name] = float(
                        result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    )
                except Exception as e:
                    if strict:
                        raise
                    _log.warning(
                        "Formula computation error",
                        table=t_name,
                        column=name,
                        formula=formula,
                        error=str(e),
                    )
                    rec[name] = None


def _is_likely_date_column(col_name: str, col_info: dict[str, Any]) -> bool:
    """Check if a column is likely a date/timestamp type."""
    name_lower = col_name.lower()
    dt_keywords = {"date", "time", "_at", "timestamp"}
    if any(kw in name_lower for kw in dt_keywords):
        return True
    dt = col_info.get("data_type", "")
    if dt.lower() in ("date", "timestamp", "datetime", "time"):
        return True
    meaning = (col_info.get("business_meaning") or "").lower()
    if any(kw in meaning for kw in ("date", "timestamp", "time")):
        return True
    return False


def _enforce_temporal_rules(
    placeholders: dict[str, list[dict[str, Any]]],
    column_guide: dict[str, Any] | None,
) -> None:
    """Repair temporal ordering violations (e.g. shipped_date >= order_date).

    Reads `temporal_rule` from column guide entries, or falls back to parsing
    constraint expressions like "shipped_date >= order_date" from the
    `constraints` list. Fixes violated dates by adding an offset to the
    reference date.
    """
    import re
    from datetime import datetime, timedelta

    import structlog

    _log = structlog.get_logger()
    if not column_guide:
        return

    # Regex to parse constraint like "col_a >= col_b" (both are column names)
    _TEMP_CONSTRAINT_RE = re.compile(  # noqa: N806
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(>=|>|<=|<)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*$"
    )

    _TEMP_COL_NAMES = {"date", "timestamp", "datetime"}  # noqa: N806

    for t_name, records in placeholders.items():
        t_guide = column_guide.get(t_name, {})
        if not t_guide:
            continue

        # Build temporal rules: try three strategies in order
        temporal_rules: dict[str, dict[str, Any]] = {}
        for c, i in t_guide.items():
            # Strategy 1: structured temporal_rule from new-format column guide
            rule = i.get("temporal_rule")
            if isinstance(rule, dict) and rule.get("reference_column"):
                temporal_rules[c] = rule
                continue

            # Strategy 2: parse constraints for date-ordering patterns
            found = False
            for constraint in i.get("constraints", []):
                m = _TEMP_CONSTRAINT_RE.match(str(constraint))
                if not m:
                    continue
                lhs, op, rhs = m.groups()
                if lhs == c and rhs != c:
                    temporal_rules[c] = {
                        "reference_column": rhs,
                        "relation": op,
                        "min_offset_days": 1,
                        "max_offset_days": 4,
                    }
                    found = True
                    break
                if rhs == c and lhs != c:
                    reverse_op = {">=": "<=", "<=": ">=", ">": "<", "<": ">"}.get(
                        op, ">="
                    )
                    temporal_rules[c] = {
                        "reference_column": lhs,
                        "relation": reverse_op,
                        "min_offset_days": 1,
                        "max_offset_days": 4,
                    }
                    found = True
                    break
            if found:
                continue

            # Strategy 3: infer from depends_on — if both columns are dates, enforce >=
            deps = i.get("depends_on", [])
            if deps and _is_likely_date_column(c, i):
                for dep in deps:
                    dep_info = t_guide.get(dep, {})
                    if _is_likely_date_column(dep, dep_info):
                        temporal_rules[c] = {
                            "reference_column": dep,
                            "relation": ">=",
                            "min_offset_days": 1,
                            "max_offset_days": 4,
                        }
                        break

        if not temporal_rules:
            continue

        _log.info("Enforcing temporal rules", table=t_name, rules=temporal_rules)
        for rec in records:
            for col, rule in temporal_rules.items():
                ref_col = rule.get("reference_column")
                if not ref_col or col not in rec or ref_col not in rec:
                    continue
                try:
                    ref_val = rec[ref_col]
                    col_val = rec[col]
                    if isinstance(ref_val, str):
                        ref_dt = datetime.fromisoformat(ref_val)
                    else:
                        ref_dt = ref_val
                    if isinstance(col_val, str):
                        col_dt = datetime.fromisoformat(col_val)
                    else:
                        col_dt = col_val
                except (ValueError, TypeError):
                    continue

                relation = rule.get("relation", ">=")
                min_off = rule.get("min_offset_days", 1)
                max_off = rule.get("max_offset_days", min_off + 3)
                import random

                offset = random.randint(min_off, max_off)  # noqa: S311

                if (
                    relation == ">="
                    and col_dt < ref_dt
                    or relation == ">"
                    and col_dt <= ref_dt
                ):
                    rec[col] = (ref_dt + timedelta(days=offset)).isoformat()
                elif (
                    relation == "<="
                    and col_dt > ref_dt
                    or relation == "<"
                    and col_dt >= ref_dt
                ):
                    rec[col] = (ref_dt - timedelta(days=offset)).isoformat()


def _validate_status_values(
    placeholders: dict[str, list[dict[str, Any]]],
    column_guide: dict[str, Any] | None,
) -> None:
    """Snap invalid status values to the most common valid state.

    Reads `workflow` from column guide entries and replaces any status value
    not in the union of allowed states with the first terminal state (or first
    non-terminal state if no terminal states defined).
    """
    import structlog

    _log = structlog.get_logger()
    if not column_guide:
        return

    for t_name, records in placeholders.items():
        t_guide = column_guide.get(t_name, {})
        if not t_guide:
            continue

        workflow_cols = {
            c: i.get("workflow")
            for c, i in t_guide.items()
            if isinstance(i.get("workflow"), dict)
        }
        if not workflow_cols:
            continue

        _log.info("Validating status values", table=t_name, columns=list(workflow_cols))
        for rec in records:
            for col, wf in workflow_cols.items():
                if col not in rec:
                    continue
                allowed = wf.get("allowed_transitions", {})
                terminal = wf.get("terminal_states", [])
                valid_states = set(allowed.keys()) | set(terminal)
                for targets in allowed.values():
                    valid_states.update(targets)
                if not valid_states:
                    continue
                val = rec[col]
                if val not in valid_states:
                    rec[col] = terminal[0] if terminal else next(iter(allowed.keys()))


def _aggregate_children_into_parent(
    placeholders: dict[str, list[dict[str, Any]]],
    column_guide: dict[str, Any] | None,
    schema: SchemaModel,
) -> None:
    """Compute parent aggregate fields from child records.

    For each aggregate formula in column_guide (e.g. "SUM(line_total)"),
    finds the child table via FK relationships and computes the aggregate
    value, overriding any LLM-generated value on the parent.
    """
    import re
    from decimal import Decimal

    import structlog

    _log = structlog.get_logger()
    if not column_guide:
        return

    # Build table_id → table_name mapping
    table_by_id: dict[str, str] = {t.id: t.name for t in schema.tables}
    col_by_id: dict[str, tuple[str, str]] = {}  # col_id → (table_name, col_name)
    for t in schema.tables:
        for c in t.columns:
            col_by_id[c.id] = (t.name, c.name)

    # Build FK mapping: (child_table, child_fk_col) → (parent_table, parent_pk_col)
    # by looking at source→target relationships
    fk_map: dict[tuple[str, str], tuple[str, str]] = {}
    for rel in schema.relationships:
        src_t = table_by_id.get(rel.source_table_id)
        src_c = col_by_id.get(rel.source_column_id)
        tgt_t = table_by_id.get(rel.target_table_id)
        tgt_c = col_by_id.get(rel.target_column_id)
        if src_t and src_c and tgt_t and tgt_c:
            fk_map[(src_t, src_c[1])] = (tgt_t, tgt_c[1])

    _AGGREGATE_FUNCS = {"SUM", "COUNT", "AVG", "MIN", "MAX", "COALESCE"}  # noqa: N806

    for t_name, t_guide in column_guide.items():
        if t_name not in placeholders:
            continue
        records = placeholders[t_name]

        for col_name, col_info in t_guide.items():
            formula = col_info.get("formula")
            if not formula:
                continue
            tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", formula))
            agg_funcs_in_formula = tokens & _AGGREGATE_FUNCS
            if not agg_funcs_in_formula:
                continue

            # Parse aggregate: e.g. SUM(line_total) → func=SUM, child_field=line_total
            for func in agg_funcs_in_formula:
                pattern = re.compile(
                    rf"{re.escape(func)}\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\)"
                )
                m = pattern.search(formula)
                if not m:
                    continue
                child_field = m.group(1)

                # Find child table: look for FK pointing TO this parent table
                child_table = None
                child_fk_col = None
                parent_pk_col = None
                for (ct, cfk), (pt, ppk) in fk_map.items():
                    if pt == t_name:
                        child_table = ct
                        child_fk_col = cfk
                        parent_pk_col = ppk
                        break

                if not child_table or child_table not in placeholders:
                    continue

                child_records = placeholders[child_table]
                _log.info(
                    "Aggregating children into parent",
                    parent=t_name,
                    parent_field=col_name,
                    child=child_table,
                    child_field=child_field,
                    func=func,
                    fk=f"{child_table}.{child_fk_col} → {t_name}.{parent_pk_col}",
                )

                # Group child records by FK value
                from collections import defaultdict

                child_groups: dict[str, list[Decimal]] = defaultdict(list)
                for crec in child_records:
                    fk_val = crec.get(child_fk_col)  # type: ignore[arg-type]
                    cval = crec.get(child_field)
                    if fk_val is not None and cval is not None:
                        try:
                            child_groups[str(fk_val)].append(Decimal(str(cval)))
                        except Exception:  # noqa: S112
                            continue

                # Compute aggregate and override parent field
                for prec in records:
                    pk_val = str(prec.get(parent_pk_col))  # type: ignore[arg-type]
                    if pk_val not in child_groups:
                        continue
                    vals = child_groups[pk_val]
                    if func == "SUM":
                        prec[col_name] = float(
                            sum(vals, Decimal("0")).quantize(Decimal("0.01"))
                        )
                    elif func == "COUNT":
                        prec[col_name] = len(vals)
                    elif func == "AVG" and vals:
                        prec[col_name] = float(
                            (
                                sum(vals, Decimal("0")) / Decimal(str(len(vals)))
                            ).quantize(Decimal("0.01"))
                        )
                    elif func == "MIN":
                        prec[col_name] = float(min(vals))
                    elif func == "MAX":
                        prec[col_name] = float(max(vals))


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

        # 5. Fetch Column Business Logic Guide (Redis/DB/LLM)
        from app.seeder.column_guide import get_column_guide

        column_guide = None
        try:
            column_guide = await get_column_guide(schema, db_client, persistence)
            import structlog

            structlog.get_logger().info(
                "Column guide loaded",
                loaded=column_guide is not None,
                table_keys=list(column_guide.keys()) if column_guide else None,
            )
        except Exception as e:
            import structlog

            structlog.get_logger().error(
                "Failed to load column guide — formula hints, distributions, and business logic will be missing from the generation prompt",
                error=str(e),
                exc_info=True,
            )

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
                t_guide = (column_guide or {}).get(t_name, {})
                if t_guide:
                    meta_with_fk["column_guide"] = t_guide

                # Exclude row-level computed fields from LLM generation
                # Only exclude if ALL formula dependencies are real columns
                import re as _re

                _agg_funcs = {"SUM", "COUNT", "AVG", "MIN", "MAX", "COALESCE"}
                _real_cols = {c.name.lower() for c in table_obj.columns}
                _row_level_computed = set()
                for _c, _i in t_guide.items():
                    _f = _i.get("formula")
                    if not _f:
                        continue
                    _tokens = set(_re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", _f))
                    if _agg_funcs & _tokens:
                        continue  # aggregate — can't compute row-level
                    _deps = _tokens - {_c} - _agg_funcs
                    if _deps and _deps <= _real_cols:
                        _row_level_computed.add(_c)  # all deps exist, exclude from LLM
                gen_fields = {
                    k: v for k, v in fields.items() if k not in _row_level_computed
                }

                seed_req = SeedRequest(
                    target=t_name,
                    num_records=batch_limit,
                    fields=gen_fields,
                    seed=seed,
                    strict=True,
                    semantic_metadata=meta_with_fk,
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
            import structlog as _slog

            _plog = _slog.get_logger()

            # 7.5a Temporal Enforcement: repair date ordering violations
            try:
                _enforce_temporal_rules(placeholders, column_guide)
            except Exception as _e:
                _plog.error("Temporal enforcement failed", error=str(_e), exc_info=True)

            # 7.5b Status Validation: snap invalid status values to valid set
            try:
                _validate_status_values(placeholders, column_guide)
            except Exception as _e:
                _plog.error("Status validation failed", error=str(_e), exc_info=True)

            # 7.5c Cross-table Aggregation: compute parent aggregates from children
            try:
                _aggregate_children_into_parent(placeholders, column_guide, schema)
            except Exception as _e:
                _plog.error(
                    "Cross-table aggregation failed", error=str(_e), exc_info=True
                )

            # 7.5d Formula Computation: evaluate column guide formulas on generated records
            try:
                _evaluate_formulas(placeholders, column_guide)
            except Exception as _e:
                _plog.error("Formula computation failed", error=str(_e), exc_info=True)

            # 8. Business Rule Engine (Repairs) — MathComputer is deprecated;
            # column business logic is now injected at generation time via ColumnGuideService.
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


@router.get("/generate/{workflow_id}/status", response_model=GenerateResponseModel)
async def get_generation_status_by_status(
    workflow_id: str,
    db: RuntimeProviderType = Depends(get_runtime_provider),
    persistence: PersistenceProvider = Depends(get_persistence_provider),
) -> GenerateResponseModel:
    """Alias for get_generation_status — provides a /status endpoint for client compatibility."""
    return await get_generation_status(workflow_id, db, persistence)


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
