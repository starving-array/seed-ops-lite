import asyncio

from app.api.endpoints.schema.validation import (
    ai_schema_assistant,
)
from app.schemas.schema_design import ColumnModel, SchemaModel, TableModel


async def run_test():
    # Small Schema
    print("=== Testing Small Schema ===")
    small_schema = SchemaModel(
        tables=[
            TableModel(
                id="t1", name="users",
                columns=[ColumnModel(id="c1", name="id", type="INTEGER", is_primary_key=True, is_nullable=False, default_value="")]
            ),
            TableModel(
                id="t2", name="orders",
                columns=[ColumnModel(id="c2", name="id", type="INTEGER", is_primary_key=True, is_nullable=False, default_value="")]
            )
        ],
        relationships=[]
    )
    res_small = await ai_schema_assistant(small_schema)
    print("Small Schema Status:", res_small.status)
    print("Small Schema Duration:", res_small.execution_duration_ms)
    print("Small Schema Summary:", res_small.summary)
    print("Suggestions:", len(res_small.suggestions))

    # Large Schema
    # print("\n=== Testing Large Schema (105 tables) ===")


if __name__ == "__main__":
    asyncio.run(run_test())
