"""Gradio web UI for SafeSeedOps Lite — mounted inside FastAPI."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

API_BASE = os.environ.get("API_BASE_URL", "")

DEMO_SCHEMAS: dict[str, Any] = {
    "e-commerce": {
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {
                        "name": "customer_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "email",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "signup_date",
                        "type": "DATE",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
            {
                "name": "orders",
                "columns": [
                    {
                        "name": "order_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "customer_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "order_date",
                        "type": "DATE",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "total",
                        "type": "DECIMAL(10,2)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "status",
                        "type": "VARCHAR(20)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
            {
                "name": "products",
                "columns": [
                    {
                        "name": "product_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(200)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "price",
                        "type": "DECIMAL(10,2)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "category",
                        "type": "VARCHAR(50)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
            {
                "name": "order_items",
                "columns": [
                    {
                        "name": "order_item_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "order_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "product_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "quantity",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
        ],
        "relationships": [
            {
                "name": "orders_customers",
                "sourceColumn": "customer_id",
                "targetTable": "customers",
                "targetColumn": "customer_id",
                "type": "many-to-one",
            },
            {
                "name": "order_items_orders",
                "sourceColumn": "order_id",
                "targetTable": "orders",
                "targetColumn": "order_id",
                "type": "many-to-one",
            },
            {
                "name": "order_items_products",
                "sourceColumn": "product_id",
                "targetTable": "products",
                "targetColumn": "product_id",
                "type": "many-to-one",
            },
        ],
    },
    "employees": {
        "tables": [
            {
                "name": "departments",
                "columns": [
                    {
                        "name": "department_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "budget",
                        "type": "DECIMAL(12,2)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
            {
                "name": "employees",
                "columns": [
                    {
                        "name": "employee_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "email",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "department_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "salary",
                        "type": "DECIMAL(10,2)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
        ],
        "relationships": [
            {
                "name": "employees_departments",
                "sourceColumn": "department_id",
                "targetTable": "departments",
                "targetColumn": "department_id",
                "type": "many-to-one",
            },
        ],
    },
    "blog": {
        "tables": [
            {
                "name": "authors",
                "columns": [
                    {
                        "name": "author_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "name",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "email",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
            {
                "name": "posts",
                "columns": [
                    {
                        "name": "post_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "title",
                        "type": "VARCHAR(200)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "author_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "published_date",
                        "type": "DATE",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
            {
                "name": "comments",
                "columns": [
                    {
                        "name": "comment_id",
                        "type": "INTEGER",
                        "isPrimaryKey": True,
                        "isNullable": False,
                    },
                    {
                        "name": "post_id",
                        "type": "INTEGER",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "author",
                        "type": "VARCHAR(100)",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                    {
                        "name": "content",
                        "type": "TEXT",
                        "isPrimaryKey": False,
                        "isNullable": False,
                    },
                ],
            },
        ],
        "relationships": [
            {
                "name": "posts_authors",
                "sourceColumn": "author_id",
                "targetTable": "authors",
                "targetColumn": "author_id",
                "type": "many-to-one",
            },
            {
                "name": "comments_posts",
                "sourceColumn": "post_id",
                "targetTable": "posts",
                "targetColumn": "post_id",
                "type": "many-to-one",
            },
        ],
    },
}


def _build_schema_state(schema_name: str) -> dict[str, Any]:
    raw = DEMO_SCHEMAS[schema_name]
    tables = []
    col_id = 1
    table_ids = {}
    for t in raw["tables"]:
        tid = f"t{col_id}"
        table_ids[t["name"]] = tid
        columns = []
        for c in t["columns"]:
            cid = f"c{col_id}"
            columns.append(
                {
                    "id": cid,
                    "name": c["name"],
                    "type": c["type"],
                    "isPrimaryKey": c["isPrimaryKey"],
                    "isNullable": c["isNullable"],
                    "defaultValue": "",
                }
            )
            col_id += 1
        tables.append({"id": tid, "name": t["name"], "columns": columns})

    rels = []
    rel_id = 1
    for r in raw["relationships"]:
        source_table_name = None
        for t in raw["tables"]:
            if any(c["name"] == r["sourceColumn"] for c in t["columns"]):
                source_table_name = t["name"]
                break
        if source_table_name is None:
            continue
        source_table_id = table_ids[source_table_name]
        target_table_id = table_ids[r["targetTable"]]
        src_col = None
        tgt_col = None
        for t in tables:
            if t["id"] == source_table_id:
                for c in t["columns"]:
                    if c["name"] == r["sourceColumn"]:
                        src_col = c["id"]
            if t["id"] == target_table_id:
                for c in t["columns"]:
                    if c["name"] == r["targetColumn"]:
                        tgt_col = c["id"]
        if src_col is None or tgt_col is None:
            continue
        rels.append(
            {
                "id": f"r{rel_id}",
                "name": r["name"],
                "sourceTableId": source_table_id,
                "sourceColumnId": src_col,
                "targetTableId": target_table_id,
                "targetColumnId": tgt_col,
                "type": r["type"],
                "isRequired": True,
                "cascadeDelete": False,
                "cascadeUpdate": False,
            }
        )
        rel_id += 1

    return {"tables": tables, "relationships": rels}


def _table_names(schema_name: str) -> list[str]:
    return [t["name"] for t in DEMO_SCHEMAS[schema_name]["tables"]]


def _schema_info(schema_name: str) -> str:
    lines = []
    for t in DEMO_SCHEMAS[schema_name]["tables"]:
        cols = ", ".join(f"{c['name']} ({c['type']})" for c in t["columns"])
        lines.append(f"**{t['name']}**: {cols}")
    rels = DEMO_SCHEMAS[schema_name]["relationships"]
    if rels:
        rlines = [
            f"{r['name']}: {r['sourceColumn']} → {r['targetTable']}.{r['targetColumn']}"
            for r in rels
        ]
        lines.append(f"\n*Relationships:* {' | '.join(rlines)}")
    return "\n\n".join(lines)


async def _check_health() -> str:
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=5) as c:
            r = await c.get("/health")
            if r.status_code == 200:
                data = r.json()
                return (
                    f"✅ **Healthy**  \n"
                    f"LLM Gateway: `{data.get('llm_status', {}).get('gateway_status', '?')}`  \n"
                    f"Uptime: `{data.get('uptime', 0):.0f}s`"
                )
            return f"⚠️ Status: {r.status_code}"
    except httpx.ConnectError:
        return "🔴 **Server unreachable** — is the app running?"
    except Exception as e:
        return f"🔴 **Error**: `{e}`"


async def _on_schema_change(schema_name: str) -> tuple[str, str]:
    info = _schema_info(schema_name)
    tables = _table_names(schema_name)
    defaults = {t: 5 for t in tables}
    return info, json.dumps(defaults, indent=2)


async def _generate(
    schema_name: str, row_targets_json: str
) -> AsyncGenerator[tuple[str, str], None]:
    try:
        row_targets = json.loads(row_targets_json) if row_targets_json.strip() else {}
    except json.JSONDecodeError as e:
        yield f"❌ Invalid JSON in row targets: {e}", ""
        return

    if not row_targets:
        yield "⚠️ Set at least one row target.", ""
        return

    schema_state = _build_schema_state(schema_name)
    yield f"⏳ Starting generation...\n\n`{json.dumps(row_targets, indent=2)}`", ""

    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=300) as c:
            payload = {
                "schemaState": schema_state,
                "rowTargets": row_targets,
                "outputFormat": "json",
            }
            resp = await c.post("/schema/generate", json=payload)
            if resp.status_code not in (200, 202):
                yield f"❌ API error: {resp.status_code}\n\n```\n{resp.text[:500]}\n```", ""
                return

            result = resp.json()
            wf_id = result.get("workflowId", "")

            for _ in range(120):
                status_resp = await c.get(f"/schema/generate/{wf_id}")
                if status_resp.status_code != 200:
                    yield f"⚠️ Status check failed: {status_resp.status_code}", ""
                    return

                status_data = status_resp.json()
                cur_status = status_data.get("status", "unknown")
                progress = status_data.get("progress", [])

                lines = [f"📊 **Status**: `{cur_status}`"]
                for p in progress:
                    tname = p.get("tableName", "?")
                    done = p.get("rowsGenerated", 0)
                    target = p.get("targetRows", 0)
                    pct = (done / target * 100) if target > 0 else 0
                    bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                    lines.append(f"  {tname:15s} [{bar}] {done}/{target} ({pct:.0f}%)")

                yield "\n".join(lines), wf_id

                errors = status_data.get("errors", [])
                if errors:
                    yield "❌ **Errors**:\n" + "\n".join(
                        f"- {e}" for e in errors
                    ), wf_id
                    return

                if cur_status in ("Completed", "Failed", "Cancelled"):
                    break
                await asyncio.sleep(2)
            else:
                yield f"⏱️ Generation still running — check `/schema/generate/{wf_id}`", wf_id
                return

            if cur_status == "Completed":
                preview_resp = await c.get(f"/schema/generate/{wf_id}/preview")
                if preview_resp.status_code == 200:
                    preview_data = preview_resp.json()
                    yield f"✅ **Generation completed!**\n\n```json\n{json.dumps(preview_data, indent=2)[:3000]}\n```", wf_id
                else:
                    yield "✅ **Generation completed!** (preview unavailable)", wf_id
            elif cur_status == "Failed":
                yield "❌ **Generation failed**", wf_id
    except httpx.TimeoutException:
        yield "⏱️ Request timed out after 5 minutes.", ""
    except Exception as e:
        yield f"❌ **Error**: `{e}`", ""


async def _download(wf_id: str) -> str:
    try:
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as c:
            resp = await c.get(f"/schema/generate/{wf_id}/download")
            if resp.status_code == 200:
                out = Path(f"generated_{wf_id}.json")
                out.write_text(resp.text, encoding="utf-8")
                return f"✅ Saved `{out.name}` ({len(resp.text)} bytes)"
            return f"❌ Download failed: {resp.status_code}"
    except Exception as e:
        return f"❌ Error: `{e}`"


GRADIO_CSS = """
.gradio-container { max-width: 960px; margin: auto; }
footer { display: none !important; }
.status-box { border-radius: 8px; padding: 16px; background: #1a1a2e; border: 1px solid #ED1C24; min-height: 100px; font-family: monospace; }
"""


def create_gradio_app() -> gr.Blocks:
    with gr.Blocks(title="SafeSeedOps Lite") as app:
        gr.Markdown(
            """
            # 🛡️ SafeSeedOps Lite
            **Enterprise Synthetic Data Generation** — PK-first, relationship-aware, LLM-powered.
            Built on *AMD ROCm + Gemma + Fireworks AI*.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🏗️ Schema")
                schema_drop = gr.Dropdown(
                    choices=list(DEMO_SCHEMAS.keys()),
                    value="e-commerce",
                    label="Schema",
                )
                schema_info = gr.Markdown(_schema_info("e-commerce"))

            with gr.Column(scale=2):
                gr.Markdown("### 📊 Row Targets")
                gr.Markdown("Enter a JSON object mapping table names to row counts.")
                row_targets = gr.Textbox(
                    value='{\n  "customers": 5,\n  "orders": 10,\n  "products": 8,\n  "order_items": 15\n}',
                    lines=6,
                    label="Row Targets (JSON)",
                )

        gen_btn = gr.Button("🚀 Generate Data", variant="primary", size="lg")
        output = gr.Markdown("*Ready.*", elem_classes="status-box")
        workflow_id = gr.State("")

        with gr.Row():
            dl_btn = gr.Button("📥 Download Last Result", size="sm")
            dl_status = gr.Markdown("")
            health_btn = gr.Button("🔍 Server Health", size="sm")
            health_box = gr.Markdown("")

        schema_drop.change(
            _on_schema_change,
            schema_drop,
            [schema_info, row_targets],
        )

        health_btn.click(_check_health, outputs=health_box)

        gen_event = gen_btn.click(
            _generate,
            inputs=[schema_drop, row_targets],
            outputs=[output, workflow_id],
        )
        gen_event.then(lambda: ("", ""), outputs=[dl_status, workflow_id])

        dl_btn.click(_download, inputs=workflow_id, outputs=dl_status)

    return app  # type: ignore[no-any-return]
