import json
from app.schemas.schema_design import ColumnModel, SchemaModel, TableModel
from app.seeder.pk_generator import PrimaryKeyGenerator

schema = SchemaModel(
    tables=[
        TableModel(
            id="t1",
            name="Users",
            columns=[
                ColumnModel(
                    id="c1", name="id", type="integer", isPrimaryKey=True, isNullable=False, defaultValue=""
                )
            ],
        ),
        TableModel(
            id="t2",
            name="Sessions",
            columns=[
                ColumnModel(
                    id="c2", name="session_id", type="uuid", isPrimaryKey=True, isNullable=False, defaultValue=""
                )
            ],
        ),
    ],
    relationships=[]
)

placeholders = {
    "Users": [
        {"_ref_id": "u1", "id": None},
        {"_ref_id": "u2", "id": None},
    ],
    "Sessions": [
        {"_ref_id": "s1", "session_id": None},
        {"_ref_id": "s2", "session_id": None},
    ],
}

PrimaryKeyGenerator.generate(schema, placeholders, start_id=1)
print(json.dumps(placeholders, indent=2))
