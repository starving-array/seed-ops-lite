import asyncio
import time
import json
import random
from typing import Any

from app.schemas.schema_design import (
    SchemaModel,
    TableModel,
    ColumnModel,
    RelationshipModel,
)
from app.agents.guardian.planner import GuardianPlanner
from app.seeder.allocator import RecordAllocator
from app.seeder.relationship_allocator import RelationshipAllocator
from app.seeder.pk_generator import PrimaryKeyGenerator
from app.seeder.fk_injector import ForeignKeyInjector
from app.seeder.math_computer import MathComputer
from app.seeder.seeder import HybridSeeder
from app.seeder.models import SeedRequest

def _col(cid, name, ctype, pk=False):
    return ColumnModel(id=cid, name=name, type=ctype, isPrimaryKey=pk, isNullable=False, defaultValue="")

# Schemas
def get_schemas():
    return {
        "E-Commerce": SchemaModel(
            tables=[
                TableModel(id="t1", name="Customers", columns=[
                    _col("c1", "id", "integer", True),
                    _col("c2", "name", "string"),
                    _col("c_d1", "created_at", "date")
                ]),
                TableModel(id="t2", name="Orders", columns=[
                    _col("c3", "order_id", "uuid", True),
                    _col("c4", "customer_id", "integer"),
                    _col("c5", "total", "float"),
                    _col("c_d2", "order_date", "date"),
                    _col("c_d3", "shipped_date", "date")
                ]),
                TableModel(id="t3", name="OrderItems", columns=[
                    _col("c6", "item_id", "auto_increment", True),
                    _col("c7", "order_id", "uuid"),
                    _col("c8", "quantity", "integer"),
                    _col("c9", "unit_price", "float"),
                    _col("c10", "subtotal", "float")
                ])
            ],
            relationships=[
                RelationshipModel(id="rel1", name="Customer_Orders", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c4", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False),
                RelationshipModel(id="rel2", name="Order_Items", sourceTableId="t2", sourceColumnId="c3", targetTableId="t3", targetColumnId="c7", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
            ]
        ),
        "Blog": SchemaModel(
            tables=[
                TableModel(id="t1", name="Users", columns=[
                    _col("c1", "id", "uuid", True),
                    _col("c2", "email", "string")
                ]),
                TableModel(id="t2", name="Posts", columns=[
                    _col("c3", "id", "uuid", True),
                    _col("c4", "user_id", "uuid"),
                    _col("c5", "content", "string")
                ]),
                TableModel(id="t3", name="Comments", columns=[
                    _col("c6", "id", "uuid", True),
                    _col("c7", "post_id", "uuid"),
                    _col("c8", "comment", "string")
                ])
            ],
            relationships=[
                RelationshipModel(id="rel1", name="User_Posts", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c4", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False),
                RelationshipModel(id="rel2", name="Post_Comments", sourceTableId="t2", sourceColumnId="c3", targetTableId="t3", targetColumnId="c7", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
            ]
        ),
        "HR": SchemaModel(
            tables=[
                TableModel(id="t1", name="Companies", columns=[
                    _col("c1", "id", "integer", True),
                    _col("c2", "name", "string")
                ]),
                TableModel(id="t2", name="Employees", columns=[
                    _col("c3", "id", "integer", True),
                    _col("c4", "company_id", "integer"),
                    _col("c5", "name", "string"),
                    _col("c_d1", "birth_date", "date"),
                    _col("c_d2", "hire_date", "date")
                ]),
                TableModel(id="t3", name="Payroll", columns=[
                    _col("c6", "id", "integer", True),
                    _col("c7", "employee_id", "integer"),
                    _col("c8", "salary", "float"),
                    _col("c9", "tax", "float"),
                    _col("c10", "subtotal", "float")
                ])
            ],
            relationships=[
                RelationshipModel(id="rel1", name="Company_Employees", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c4", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False),
                RelationshipModel(id="rel2", name="Employee_Payroll", sourceTableId="t2", sourceColumnId="c3", targetTableId="t3", targetColumnId="c7", type="1:1", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
            ]
        )
    }

async def run_audit():
    schemas = get_schemas()
    seeder = HybridSeeder()
    
    from app.cli.runner import map_column_to_field_def
    from app.agents.schema_validation.models import SchemaValidationReport
    
    report_dict = {}
    
    for schema_name, schema in schemas.items():
        print(f"\\n--- Auditing Schema: {schema_name} ---")
        row_targets = {t.name: 3 for t in schema.tables} # Use 3 for speed
        
        ordered_tables = [t.name for t in schema.tables]
        print(f"Ordered Tables: {ordered_tables}")
        
        # 2. Placeholders
        placeholders = RecordAllocator.allocate(schema, ordered_tables, row_targets)
        
        # 3. Relationships
        relationship_map = RelationshipAllocator.allocate(schema, placeholders, 42)
        
        from app.seeder.semantic_analyzer import SemanticAnalyzer
        semantic_metadata = SemanticAnalyzer.analyze(schema)
        
        from app.seeder.domain_intelligence import DomainIntelligenceEngine
        domain_context = DomainIntelligenceEngine.analyze(schema)
        
        # 4. Generate Business Data
        for t_name in ordered_tables:
            table_obj = next(t for t in schema.tables if t.name == t_name)
            fields = {}
            for col in table_obj.columns:
                if col.is_primary_key:
                    continue
                is_fk = False
                for rel in schema.relationships:
                    if rel.source_table_id == table_obj.id and rel.source_column_id == col.id:
                        is_fk = True
                        break
                    if rel.target_table_id == table_obj.id and rel.target_column_id == col.id:
                        is_fk = True
                        break
                if is_fk:
                    continue
                fields[col.name] = map_column_to_field_def(col.name, col.type, col.is_primary_key)
                
            req = SeedRequest(
                target=t_name,
                num_records=row_targets[t_name],
                fields=fields,
                seed=42,
                strict=True,
                semantic_metadata=semantic_metadata.get(t_name, {}),
                domain_context=domain_context,
            )
            res = await seeder.seed(req)
            if res.success:
                for i, r in enumerate(res.records):
                    placeholders[t_name][i].update(r.data)
                    
        # 5. PKs
        PrimaryKeyGenerator.generate(schema, placeholders, 1)
        
        # 6. FKs
        ForeignKeyInjector.inject(schema, placeholders, relationship_map)
        
        # 7. Math
        MathComputer.compute(schema, placeholders)
        
        # 8. Business Rule Engine
        from app.seeder.business_rules import BusinessRuleEngine
        repair_stats = BusinessRuleEngine.enforce(schema, placeholders, semantic_metadata)
        print(f"Repairs: {repair_stats}")
        
        # Save output
        clean_records = {}
        for t in ordered_tables:
            clean_records[t] = [{k: v for k, v in p.items() if not k.startswith("_")} for p in placeholders[t]]
            
        report_dict[schema_name] = clean_records
        
    with open("audit_results.json", "w") as f:
        json.dump(report_dict, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_audit())
