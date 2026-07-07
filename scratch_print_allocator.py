import json
from app.schemas.schema_design import ColumnModel, SchemaModel, TableModel
from app.seeder.allocator import RecordAllocator

schema = SchemaModel(
    tables=[
        TableModel(
            id="t1",
            name="Customers",
            columns=[
                ColumnModel(
                    id="c1",
                    name="id",
                    type="integer",
                    isPrimaryKey=True,
                    isNullable=False,
                    defaultValue="",
                ),
                ColumnModel(
                    id="c2",
                    name="name",
                    type="string",
                    isPrimaryKey=False,
                    isNullable=False,
                    defaultValue="",
                ),
            ],
        ),
        TableModel(
            id="t2",
            name="Orders",
            columns=[
                ColumnModel(
                    id="c3",
                    name="order_id",
                    type="integer",
                    isPrimaryKey=True,
                    isNullable=False,
                    defaultValue="",
                ),
                ColumnModel(
                    id="c4",
                    name="customer_id",
                    type="integer",
                    isPrimaryKey=False,
                    isNullable=False,
                    defaultValue="",
                ),
            ],
        ),
    ],
    relationships=[],
)

ordered_tables = ["Customers", "Orders"]
row_targets = {"Customers": 4, "Orders": 10}

allocated = RecordAllocator.allocate(schema, ordered_tables, row_targets)
print(json.dumps(allocated, indent=2))
