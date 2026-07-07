import json
from app.schemas.schema_design import ColumnModel, RelationshipModel, SchemaModel, TableModel
from app.seeder.relationship_allocator import RelationshipAllocator

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
                )
            ],
        ),
        TableModel(
            id="t2",
            name="Orders",
            columns=[
                ColumnModel(
                    id="c2",
                    name="order_id",
                    type="integer",
                    isPrimaryKey=True,
                    isNullable=False,
                    defaultValue="",
                )
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
            targetColumnId="c2",
            type="1:n",
            isRequired=True,
            cascadeDelete=False,
            cascadeUpdate=False,
        )
    ],
)

placeholders = {
    "Customers": [
        {"_ref_id": "Customer[0]", "_table": "Customers", "_index": 0},
        {"_ref_id": "Customer[1]", "_table": "Customers", "_index": 1}
    ],
    "Orders": [
        {"_ref_id": "Order[0]", "_table": "Orders", "_index": 0},
        {"_ref_id": "Order[1]", "_table": "Orders", "_index": 1},
        {"_ref_id": "Order[2]", "_table": "Orders", "_index": 2},
        {"_ref_id": "Order[3]", "_table": "Orders", "_index": 3},
        {"_ref_id": "Order[4]", "_table": "Orders", "_index": 4},
        {"_ref_id": "Order[5]", "_table": "Orders", "_index": 5},
    ],
}

allocated = RelationshipAllocator.allocate(schema, placeholders, seed=123)
print(json.dumps(allocated, indent=2))
