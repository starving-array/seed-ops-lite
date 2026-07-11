#!/usr/bin/env python3
"""SafeSeedOps Lite — interactive CLI demo wizard for the AMD Hackathon.

Connects to a running SafeSeedOps API server and demonstrates
synthetic data generation with pre-built schemas.

Usage:
    # Start the API server first:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

    # Then run the wizard:
    python scripts/demo_wizard.py
    python scripts/demo_wizard.py --url http://localhost:8000
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

# ── Demo schemas (wizard uses a simpler representation) ──

DEMO_SCHEMAS: dict[str, dict] = {
    "e-commerce": {
        "description": "Customers → Orders → Order Items → Products",
        "tables": [
            {
                "name": "customers",
                "columns": [
                    {"name": "customer_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "name", "type": "VARCHAR(100)"},
                    {"name": "email", "type": "VARCHAR(100)"},
                    {"name": "signup_date", "type": "DATE"},
                ],
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "order_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "customer_id", "type": "INTEGER"},
                    {"name": "order_date", "type": "DATE"},
                    {"name": "total", "type": "DECIMAL(10,2)"},
                    {"name": "status", "type": "VARCHAR(20)"},
                ],
            },
            {
                "name": "products",
                "columns": [
                    {"name": "product_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "name", "type": "VARCHAR(200)"},
                    {"name": "price", "type": "DECIMAL(10,2)"},
                    {"name": "category", "type": "VARCHAR(50)"},
                ],
            },
            {
                "name": "order_items",
                "columns": [
                    {"name": "order_item_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "order_id", "type": "INTEGER"},
                    {"name": "product_id", "type": "INTEGER"},
                    {"name": "quantity", "type": "INTEGER"},
                ],
            },
        ],
        "relationships": [
            {"name": "orders_customers", "sourceTable": "orders", "sourceColumn": "customer_id", "targetTable": "customers", "targetColumn": "customer_id", "type": "many-to-one"},
            {"name": "order_items_orders", "sourceTable": "order_items", "sourceColumn": "order_id", "targetTable": "orders", "targetColumn": "order_id", "type": "many-to-one", "cascadeDelete": True},
            {"name": "order_items_products", "sourceTable": "order_items", "sourceColumn": "product_id", "targetTable": "products", "targetColumn": "product_id", "type": "many-to-one"},
        ],
    },
    "employees": {
        "description": "Departments → Employees",
        "tables": [
            {
                "name": "departments",
                "columns": [
                    {"name": "dept_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "name", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "employees",
                "columns": [
                    {"name": "emp_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "name", "type": "VARCHAR(100)"},
                    {"name": "dept_id", "type": "INTEGER"},
                    {"name": "salary", "type": "DECIMAL(10,2)"},
                    {"name": "hire_date", "type": "DATE"},
                ],
            },
        ],
        "relationships": [
            {"name": "employees_departments", "sourceTable": "employees", "sourceColumn": "dept_id", "targetTable": "departments", "targetColumn": "dept_id", "type": "many-to-one"},
        ],
    },
    "blog": {
        "description": "Authors → Posts → Comments",
        "tables": [
            {
                "name": "authors",
                "columns": [
                    {"name": "author_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "name", "type": "VARCHAR(100)"},
                    {"name": "email", "type": "VARCHAR(100)"},
                ],
            },
            {
                "name": "posts",
                "columns": [
                    {"name": "post_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "author_id", "type": "INTEGER"},
                    {"name": "title", "type": "VARCHAR(200)"},
                    {"name": "content", "type": "TEXT"},
                    {"name": "published_date", "type": "DATE"},
                ],
            },
            {
                "name": "comments",
                "columns": [
                    {"name": "comment_id", "type": "INTEGER", "isPrimaryKey": True},
                    {"name": "post_id", "type": "INTEGER"},
                    {"name": "author_name", "type": "VARCHAR(100)"},
                    {"name": "body", "type": "TEXT"},
                    {"name": "created_at", "type": "TIMESTAMP"},
                ],
            },
        ],
        "relationships": [
            {"name": "posts_authors", "sourceTable": "posts", "sourceColumn": "author_id", "targetTable": "authors", "targetColumn": "author_id", "type": "many-to-one"},
            {"name": "comments_posts", "sourceTable": "comments", "sourceColumn": "post_id", "targetTable": "posts", "targetColumn": "post_id", "type": "many-to-one", "cascadeDelete": True},
        ],
    },
}


def _banner() -> None:
    print()
    print("  +-----------------------------------------------+")
    print("  |     SafeSeedOps Lite -- Demo Wizard           |")
    print("  |   AMD Developer Hackathon 2026  Track 3      |")
    print("  +-----------------------------------------------+")
    print()


def _pick(options: list[str], title: str = "Select an option") -> str:
    print(f"\n  {title}:")
    for i, opt in enumerate(options, 1):
        desc = ""
        if opt in DEMO_SCHEMAS:
            desc = f"  ({DEMO_SCHEMAS[opt]['description']})"
        label = opt if not desc else f"{opt:<20}{desc}"
        print(f"    {i}. {label}")
    while True:
        try:
            idx = int(input(f"\n  Enter number (1-{len(options)}): "))
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print("  Invalid choice, try again.")


async def _health(api_url: str) -> dict | None:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{api_url}/health", timeout=5)
            if r.is_success:
                return r.json()
    except Exception:
        pass
    return None


async def _providers(api_url: str) -> list[dict] | None:
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{api_url}/llm/providers", timeout=5)
            if r.is_success:
                return r.json()
    except Exception:
        pass
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description="SafeSeedOps Lite Demo Wizard")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    api = args.url.rstrip("/")

    _banner()

    # Check API health
    health = await _health(api)
    if not health:
        print(f"  ✗ Cannot reach API at {api}")
        print(f"    Start the server:  uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    print(f"  ✓ API healthy at {api}")
    print()

    # Pick schema
    names = list(DEMO_SCHEMAS)
    choice = _pick(names, "Choose a demo schema")
    schema_def = DEMO_SCHEMAS[choice]

    print(f"\n  Schema: {choice}")
    tables_str = ", ".join(t["name"] for t in schema_def["tables"])
    print(f"  Tables: {tables_str} ({len(schema_def['tables'])})")
    print(f"  Relationships: {len(schema_def.get('relationships', []))}")

    # Row targets
    print("\n  ── Row Targets ──")
    targets: dict[str, int] = {}
    for t in schema_def["tables"]:
        default = 50
        for r in schema_def.get("relationships", []):
            if r["sourceTable"] == t["name"]:
                default = 200
                break
        val = input(f"  Rows for '{t['name']}' [{default}]: ").strip()
        targets[t["name"]] = int(val) if val else default

    # Confirm
    print(f"\n  {'─'*50}")
    print(f"  Schema:  {choice}")
    print(f"  Tables:  {tables_str}")
    print(f"  Targets: {json.dumps(targets)}")
    print(f"  {'─'*50}")
    if input("\n  Start generation? (Y/n): ").strip().lower() == "n":
        print("  Cancelled.")
        return

    # Build column ID lookup: (table_name, column_name) -> column_id
    col_id_map: dict[tuple[str, str], str] = {}
    for i, t in enumerate(schema_def["tables"]):
        for j, c in enumerate(t["columns"]):
            col_id_map[(t["name"], c["name"])] = f"c{i}_{j}"

    # Build minimal payload accepted by /schema/generate
    # The API expects schemaState with full table/column/relationship models
    payload = {
        "schemaState": {
            "tables": [
                {
                    "id": f"t{i}",
                    "name": t["name"],
                    "columns": [
                        {
                            "id": f"c{i}_{j}",
                            "name": c["name"],
                            "type": c["type"],
                            "isPrimaryKey": c.get("isPrimaryKey", False),
                            "isNullable": False,
                            "defaultValue": "",
                        }
                        for j, c in enumerate(t["columns"])
                    ],
                }
                for i, t in enumerate(schema_def["tables"])
            ],
            "relationships": [
                {
                    "id": f"r{ri}",
                    "name": r["name"],
                    "sourceTableId": f"t{next(i for i, t in enumerate(schema_def['tables']) if t['name'] == r['sourceTable'])}",
                    "sourceColumnId": col_id_map[(r["sourceTable"], r["sourceColumn"])],
                    "targetTableId": f"t{next(i for i, t in enumerate(schema_def['tables']) if t['name'] == r['targetTable'])}",
                    "targetColumnId": col_id_map[(r["targetTable"], r["targetColumn"])],
                    "type": r["type"],
                    "isRequired": True,
                    "cascadeDelete": r.get("cascadeDelete", False),
                    "cascadeUpdate": False,
                }
                for ri, r in enumerate(schema_def.get("relationships", []))
            ],
        },
        "rowTargets": targets,
        "outputFormat": "json",
    }

    # Call the API
    print("\n  Generating synthetic data...")
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(f"{api}/schema/generate", json=payload)
            elapsed = time.perf_counter() - start

            if resp.is_success:
                result = resp.json()
                wf_id = result.get("workflowId", "?")
                print(f"\n  ✓ Generation completed in {elapsed:.1f}s")
                print(f"  Workflow ID: {wf_id}")
                print(f"  Status: {result.get('status', '?')}")
                print(f"  Total rows: {result.get('totalRowsGenerated', '?')}")
                for p in result.get("progress", []):
                    print(f"    {p['tableName']}: {p['rowsGenerated']} rows")

                # Download
                if input("\n  Download results? (Y/n): ").strip().lower() != "n":
                    dl_resp = await client.get(f"{api}/schema/generate/{wf_id}/download")
                    if dl_resp.is_success:
                        out_dir = Path("./demo_output")
                        out_dir.mkdir(exist_ok=True)
                        out_path = out_dir / f"{choice}_{wf_id[:8]}.json"
                        with open(out_path, "w") as f:
                            json.dump(dl_resp.json(), f, indent=2, default=str)
                        print(f"  Saved to {out_path}")
                    else:
                        # Try preview instead
                        prev = await client.get(f"{api}/schema/generate/{wf_id}/preview")
                        if prev.is_success:
                            data = prev.json()
                            print("  Preview (first 3 rows per table):")
                            for table_name, rows in data.items():
                                print(f"\n    ── {table_name} ──")
                                for row in rows[:3]:
                                    print(f"      {json.dumps(row)}")
            else:
                print(f"\n  ✗ API error: HTTP {resp.status_code}")
                print(f"    {resp.text[:500]}")
    except httpx.ConnectError:
        print(f"\n  ✗ Cannot connect to {api}. Is the server running?")
    except Exception as exc:
        print(f"\n  ✗ Error: {exc}")

    print("\n  Visit http://localhost:8000/docs for the full API.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
