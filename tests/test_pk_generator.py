"""Unit tests for PrimaryKeyGenerator."""

from app.schemas.schema_design import ColumnModel, SchemaModel, TableModel
from app.seeder.pk_generator import PrimaryKeyGenerator


def test_pk_generation():
    """Test deterministic generation of PKs (Integer, UUID, GUID, Auto Increment)."""
    schema = SchemaModel(
        tables=[
            TableModel(
                id="t1",
                name="Users",
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
                        id="c1b",
                        name="email",
                        type="string",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
            TableModel(
                id="t2",
                name="Sessions",
                columns=[
                    ColumnModel(
                        id="c2",
                        name="session_id",
                        type="uuid",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            ),
            TableModel(
                id="t3",
                name="Tokens",
                columns=[
                    ColumnModel(
                        id="c3",
                        name="guid_id",
                        type="guid",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            ),
            TableModel(
                id="t4",
                name="Logs",
                columns=[
                    ColumnModel(
                        id="c4",
                        name="log_id",
                        type="auto_increment",
                        isPrimaryKey=True,
                        isNullable=False,
                        defaultValue="",
                    )
                ],
            ),
        ],
        relationships=[],
    )

    placeholders = {
        "Users": [
            {"_ref_id": "u1", "id": None, "email": "test1@example.com"},
            {"_ref_id": "u2", "id": None, "email": "test2@example.com"},
        ],
        "Sessions": [
            {"_ref_id": "s1", "session_id": None},
        ],
        "Tokens": [
            {"_ref_id": "t1", "guid_id": None},
        ],
        "Logs": [
            {"_ref_id": "l1", "log_id": None},
            {"_ref_id": "l2", "log_id": None},
        ],
    }

    PrimaryKeyGenerator.generate(schema, placeholders, start_id=100)

    # Integer check — global sequence spans all tables
    # Users: 100, 101 | Sessions(uuid): 102 | Tokens(guid): 103 | Logs(int): 104, 105
    assert placeholders["Users"][0]["id"] == 100
    assert placeholders["Users"][1]["id"] == 101

    # UUID check
    sess_id = placeholders["Sessions"][0]["session_id"]
    assert isinstance(sess_id, str)
    assert len(sess_id) == 36

    # GUID check
    guid_id = placeholders["Tokens"][0]["guid_id"]
    assert isinstance(guid_id, str)
    assert len(guid_id) == 36

    # Logs — sequence continued after Users(2) + Sessions(1) + Tokens(1) = 4 consumed
    assert placeholders["Logs"][0]["log_id"] == 104
    assert placeholders["Logs"][1]["log_id"] == 105

    # Deterministic check — same sequence positioning yields same values
    placeholders_2 = {
        "Users": [
            {"_ref_id": "u1", "id": None, "email": ""},
            {"_ref_id": "u2", "id": None, "email": ""},
        ],
        "Sessions": [{"_ref_id": "s1", "session_id": None}],
        "Tokens": [{"_ref_id": "t1", "guid_id": None}],
        "Logs": [
            {"_ref_id": "l1", "log_id": None},
            {"_ref_id": "l2", "log_id": None},
        ],
    }
    PrimaryKeyGenerator.generate(schema, placeholders_2, start_id=100)
    assert placeholders_2["Sessions"][0]["session_id"] == sess_id
    assert placeholders_2["Users"][0]["id"] == 100
    assert placeholders_2["Logs"][0]["log_id"] == 104
