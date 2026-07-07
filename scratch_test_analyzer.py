import json

from app.schemas.schema_design import SchemaModel, TableModel, ColumnModel, RelationshipModel
from app.seeder.semantic_analyzer import SemanticAnalyzer

def _col(cid, name, ctype, pk=False):
    return ColumnModel(id=cid, name=name, type=ctype, isPrimaryKey=pk, isNullable=False, defaultValue="")

schemas = {
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
            RelationshipModel(id="rel1", name="rel", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c4", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False),
            RelationshipModel(id="rel2", name="rel", sourceTableId="t2", sourceColumnId="c3", targetTableId="t3", targetColumnId="c7", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
        ]
    ),
    "HR": SchemaModel(
        tables=[
            TableModel(id="t1", name="Employees", columns=[
                _col("c1", "id", "integer", True),
                _col("c2", "name", "string"),
                _col("c3", "birth_date", "date"),
                _col("c4", "hire_date", "date")
            ]),
            TableModel(id="t2", name="Payroll", columns=[
                _col("c5", "id", "integer", True),
                _col("c6", "employee_id", "integer"),
                _col("c7", "salary", "float"),
                _col("c8", "currency", "string")
            ])
        ],
        relationships=[
            RelationshipModel(id="rel1", name="rel", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c6", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
        ]
    ),
    "Hospital": SchemaModel(
        tables=[
            TableModel(id="t1", name="Patients", columns=[
                _col("c1", "id", "integer", True),
                _col("c2", "name", "string")
            ]),
            TableModel(id="t2", name="Visits", columns=[
                _col("c3", "id", "integer", True),
                _col("c4", "patient_id", "integer"),
                _col("c5", "visit_date", "date"),
                _col("c6", "discharge_date", "date"),
                _col("c7", "status", "string"),
                _col("c8", "completed_at", "date")
            ])
        ],
        relationships=[
            RelationshipModel(id="rel1", name="rel", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c4", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
        ]
    ),
    "Blog": SchemaModel(
        tables=[
            TableModel(id="t1", name="Users", columns=[
                _col("c1", "id", "integer", True),
                _col("c2", "username", "string")
            ]),
            TableModel(id="t2", name="Posts", columns=[
                _col("c3", "id", "integer", True),
                _col("c4", "user_id", "integer"),
                _col("c5", "title", "string"),
                _col("c6", "created_at", "date"),
                _col("c7", "updated_at", "date")
            ])
        ],
        relationships=[
            RelationshipModel(id="rel1", name="rel", sourceTableId="t1", sourceColumnId="c1", targetTableId="t2", targetColumnId="c4", type="1:n", isRequired=True, cascadeDelete=False, cascadeUpdate=False)
        ]
    ),
    "Education": SchemaModel(
        tables=[
            TableModel(id="t1", name="Invoices", columns=[
                _col("c1", "id", "integer", True),
                _col("c2", "student_id", "integer"),
                _col("c3", "invoice_date", "date"),
                _col("c4", "due_date", "date"),
                _col("c5", "total", "float")
            ])
        ],
        relationships=[]
    )
}

if __name__ == "__main__":
    report = {}
    for name, schema in schemas.items():
        report[name] = SemanticAnalyzer.analyze(schema)
    print(json.dumps(report, indent=2))
