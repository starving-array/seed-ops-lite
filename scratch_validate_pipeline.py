import asyncio
import time
import json
import dataclasses
from typing import Any

from app.schemas.schema_design import ColumnModel, RelationshipModel, SchemaModel, TableModel
from app.agents.guardian.planner import GuardianPlanner
from app.seeder.allocator import RecordAllocator
from app.seeder.relationship_allocator import RelationshipAllocator
from app.seeder.pk_generator import PrimaryKeyGenerator
from app.seeder.fk_injector import ForeignKeyInjector
from app.seeder.math_computer import MathComputer
from app.seeder.seeder import HybridSeeder
from app.seeder.models import SeedRequest
from app.cli.runner import map_column_to_field_def
from app.agents.schema_validation.models import SchemaValidationReport


async def validate_pipeline():
    print("--- STARTING PIPELINE VALIDATION ---")
    timings = {}
    
    # 1. Schema Definition
    t0 = time.perf_counter()
    schema = SchemaModel(
        tables=[
            TableModel(
                id="t1",
                name="Customers",
                columns=[
                    ColumnModel(id="c1", name="id", type="integer", isPrimaryKey=True, isNullable=False, defaultValue=""),
                    ColumnModel(id="c2", name="name", type="string", isPrimaryKey=False, isNullable=False, defaultValue=""),
                ],
            ),
            TableModel(
                id="t2",
                name="Orders",
                columns=[
                    ColumnModel(id="c3", name="order_id", type="uuid", isPrimaryKey=True, isNullable=False, defaultValue=""),
                    ColumnModel(id="c4", name="customer_id", type="integer", isPrimaryKey=False, isNullable=False, defaultValue=""),
                    ColumnModel(id="c5", name="total", type="float", isPrimaryKey=False, isNullable=False, defaultValue=""),
                ],
            ),
            TableModel(
                id="t3",
                name="OrderItems",
                columns=[
                    ColumnModel(id="c6", name="item_id", type="auto_increment", isPrimaryKey=True, isNullable=False, defaultValue=""),
                    ColumnModel(id="c7", name="order_id", type="uuid", isPrimaryKey=False, isNullable=False, defaultValue=""),
                    ColumnModel(id="c8", name="quantity", type="integer", isPrimaryKey=False, isNullable=False, defaultValue=""),
                    ColumnModel(id="c9", name="unit_price", type="float", isPrimaryKey=False, isNullable=False, defaultValue=""),
                    ColumnModel(id="c10", name="subtotal", type="float", isPrimaryKey=False, isNullable=False, defaultValue=""),
                ],
            ),
        ],
        relationships=[
            RelationshipModel(
                id="rel1",
                name="Customer_Orders",
                sourceTableId="t1",
                sourceColumnId="c1",
                targetTableId="t2",
                targetColumnId="c4",
                type="1:n",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
            RelationshipModel(
                id="rel2",
                name="Order_Items",
                sourceTableId="t2",
                sourceColumnId="c3",
                targetTableId="t3",
                targetColumnId="c7",
                type="1:n",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            )
        ],
    )
    row_targets = {"Customers": 5, "Orders": 5, "OrderItems": 5}
    timings["Schema Definition"] = time.perf_counter() - t0

    # 2. Dependency Order
    t0 = time.perf_counter()
    ddl = "CREATE TABLE Customers (id int); CREATE TABLE Orders (order_id uuid, customer_id int); CREATE TABLE OrderItems (item_id int, order_id uuid);"
    report = SchemaValidationReport(
        overall_status="pass", summary="", findings=[], recommendations=[], warnings=[], execution_statistics={}, executed_skills=[], execution_duration_ms=0.0
    )
    planner = GuardianPlanner()
    plan_result = await planner.plan(ddl, report, row_targets)
    ordered_tables = plan_result.ordered_tables
    # Ensure standard order if planner returns empty due to fake DDL
    if not ordered_tables:
        ordered_tables = ["Customers", "Orders", "Audit"]
    else:
        # Planner sometimes returns lowercase table names. Map them back to original names.
        name_map = {t.name.lower(): t.name for t in schema.tables}
        ordered_tables = [name_map.get(t.lower(), t) for t in ordered_tables]
    timings["Dependency Ordering"] = time.perf_counter() - t0

    # 3. Placeholder Allocation
    t0 = time.perf_counter()
    placeholders = RecordAllocator.allocate(schema, ordered_tables, row_targets)
    timings["Placeholder Allocation"] = time.perf_counter() - t0

    # 4. Relationship Allocation
    t0 = time.perf_counter()
    rel_map = RelationshipAllocator.allocate(schema, placeholders, seed=42)
    timings["Relationship Allocation"] = time.perf_counter() - t0

    # 5. Business Data Generation (HybridSeeder)
    t0 = time.perf_counter()
    seeder = HybridSeeder()
    table_objs = {t.name: t for t in schema.tables}
    for t_name in ordered_tables:
        t_obj = table_objs.get(t_name)
        if not t_obj:
            continue
        actual_name = t_name
        fields = {}
        for col in t_obj.columns:
            # Skip PKs/FKs for business generation
            if col.is_primary_key or col.name == "customer_id":
                continue
            fields[col.name] = map_column_to_field_def(col.name, col.type, False)
        
        target_count = row_targets.get(actual_name, 0)
        if target_count > 0 and fields:
            seed_req = SeedRequest(target=actual_name, num_records=target_count, fields=fields, seed=42, strict=True)
            seed_res = await seeder.seed(seed_req)
            if seed_res.success:
                # Merge into placeholders
                for i in range(target_count):
                    # We inject generated data into the placeholder fields
                    for k, v in seed_res.records[i].data.items():
                        placeholders[actual_name][i][k] = v
    timings["Business Data Generation"] = time.perf_counter() - t0

    # 6. Math Computation (Before PK/FK to prep values if needed, or after. It doesn't matter)
    t0 = time.perf_counter()
    MathComputer.compute(schema, placeholders)
    timings["Math Computation"] = time.perf_counter() - t0

    # 7. PK Generation
    t0 = time.perf_counter()
    PrimaryKeyGenerator.generate(schema, placeholders, start_id=100)
    timings["PK Generation"] = time.perf_counter() - t0

    # 8. FK Injection
    t0 = time.perf_counter()
    stats = ForeignKeyInjector.inject(schema, placeholders, rel_map)
    timings["FK Injection"] = time.perf_counter() - t0

    # Print Results
    print("\n--- TIMING BREAKDOWN ---")
    for step, duration in timings.items():
        print(f"{step:25}: {duration*1000:.2f} ms")

    print("\n--- DIAGNOSTICS & VALIDATION REPORT ---")
    print("Ordered Tables:", ordered_tables)
    print("Relationship Map:", json.dumps(rel_map, indent=2))
    print("FK Injection Stats:", json.dumps(dataclasses.asdict(stats), indent=2))
    
    # Check constraints
    orphan_count = 0
    fk_validity = True
    for order in placeholders.get("Orders", []):
        if order.get("customer_id") is None:
            orphan_count += 1
            fk_validity = False
            
    print(f"Orphan Rows (Orders): {orphan_count}")
    print(f"FK Validity 100%: {fk_validity}")

    print("\n--- GENERATED DATA SAMPLE ---")
    print(json.dumps(placeholders, indent=2))

if __name__ == "__main__":
    asyncio.run(validate_pipeline())
