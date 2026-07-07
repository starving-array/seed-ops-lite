import json
import dataclasses
from app.schemas.schema_design import ColumnModel, RelationshipModel, SchemaModel, TableModel
from app.seeder.fk_injector import ForeignKeyInjector

schema = SchemaModel(
    tables=[
        TableModel(
            id="t1",
            name="Customers",
            columns=[
                ColumnModel(
                    id="c1", name="id", type="integer", isPrimaryKey=True, isNullable=False, defaultValue=""
                )
            ],
        ),
        TableModel(
            id="t2",
            name="Orders",
            columns=[
                ColumnModel(
                    id="c2", name="order_id", type="integer", isPrimaryKey=True, isNullable=False, defaultValue=""
                ),
                ColumnModel(
                    id="c3", name="customer_id", type="integer", isPrimaryKey=False, isNullable=False, defaultValue=""
                ),
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
            targetColumnId="c3",
            type="1:n",
            isRequired=True,
            cascadeDelete=False,
            cascadeUpdate=False,
        )
    ],
)

placeholders = {
    "Customers": [
        {"_ref_id": "Customer[0]", "id": 100},
        {"_ref_id": "Customer[1]", "id": 200}
    ],
    "Orders": [
        {"_ref_id": "Order[0]", "order_id": 500, "customer_id": None},
        {"_ref_id": "Order[1]", "order_id": 501, "customer_id": None},
        {"_ref_id": "Order[2]", "order_id": 502, "customer_id": None},
    ],
}

relationship_map = {
    "Customer_Orders": {
        "Customer[0]": ["Order[0]", "Order[2]"],
        "Customer[1]": ["Order[1]"]
    }
}

stats = ForeignKeyInjector.inject(schema, placeholders, relationship_map)
print("--- INJECTION STATS ---")
print(json.dumps(dataclasses.asdict(stats), indent=2))
print("--- CHILD RECORDS ---")
print(json.dumps(placeholders["Orders"], indent=2))
