"""Unit tests for the SemanticAnalyzer."""

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.seeder.semantic_analyzer import SemanticAnalyzer


def _make_table(
    tid: str,
    name: str,
    columns: list[tuple[str, str, bool]],
) -> TableModel:
    return TableModel(
        id=tid,
        name=name,
        columns=[
            ColumnModel(
                id=cid,
                name=cname,
                type=ctype,
                isPrimaryKey=ispk,
                isNullable=False,
                defaultValue="",
            )
            for cid, cname, ctype, ispk in columns
        ],
    )


class TestAnalyze:
    def test_primary_keys_extracted(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "users", [("c1", "id", "integer", True)]),
                _make_table("t2", "orders", [("c2", "order_id", "integer", True)]),
            ],
            relationships=[],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert meta["users"]["primary_keys"] == ["id"]
        assert meta["orders"]["primary_keys"] == ["order_id"]

    def test_foreign_keys_extracted(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "users", [("c1", "id", "integer", True)]),
                _make_table(
                    "t2",
                    "orders",
                    [
                        ("c2", "order_id", "integer", True),
                        ("c3", "user_id", "integer", False),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="user_orders",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t2",
                    targetColumnId="c3",
                    type="1:n",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert "user_id" in meta["orders"]["foreign_keys"]
        assert "users" in meta["orders"]["depends_on"]

    def test_depends_on_inferred(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "parent", [("c1", "id", "integer", True)]),
                _make_table(
                    "t2",
                    "child",
                    [
                        ("c2", "child_id", "integer", True),
                        ("c3", "parent_id", "integer", False),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="parent_child",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t2",
                    targetColumnId="c3",
                    type="1:n",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert meta["child"]["depends_on"] == ["parent"]
        assert meta["parent"]["depends_on"] == []

    def test_n1_reversed_dependency(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "detail", [("c1", "id", "integer", True)]),
                _make_table(
                    "t2",
                    "master",
                    [
                        ("c2", "master_id", "integer", True),
                        ("c3", "detail_id", "integer", False),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="detail_master",
                    sourceTableId="t2",
                    sourceColumnId="c3",
                    targetTableId="t1",
                    targetColumnId="c1",
                    type="n:1",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert meta["master"]["depends_on"] == ["detail"]
        assert meta["detail"]["depends_on"] == []

    def test_self_reference_detected(self):
        schema = SchemaModel(
            tables=[
                _make_table(
                    "t1",
                    "employee",
                    [
                        ("c1", "id", "integer", True),
                        ("c2", "manager_id", "integer", False),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="self_mgr",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t1",
                    targetColumnId="c2",
                    type="1:n",
                    isRequired=False,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert meta["employee"]["self_reference"] is True
        assert len(meta["employee"]["self_reference_columns"]) >= 1

    def test_junction_table_detected(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "student", [("c1", "id", "integer", True)]),
                _make_table("t2", "course", [("c2", "id", "integer", True)]),
                _make_table(
                    "t3",
                    "enrollment",
                    [
                        ("c3", "student_id", "integer", True),
                        ("c4", "course_id", "integer", True),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="enrollment_student",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t3",
                    targetColumnId="c3",
                    type="1:n",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
                RelationshipModel(
                    id="r2",
                    name="enrollment_course",
                    sourceTableId="t2",
                    sourceColumnId="c2",
                    targetTableId="t3",
                    targetColumnId="c4",
                    type="1:n",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert meta["enrollment"]["junction_table"] is True

    def test_non_junction_composite_pk_not_marked(self):
        schema = SchemaModel(
            tables=[
                _make_table(
                    "t1",
                    "order_item",
                    [
                        ("c1", "order_id", "integer", True),
                        ("c2", "line_num", "integer", True),
                        ("c3", "product", "string", False),
                    ],
                ),
            ],
            relationships=[],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert meta["order_item"]["junction_table"] is False

    def test_circular_dependency_detected(self):
        schema = SchemaModel(
            tables=[
                _make_table(
                    "t1",
                    "project",
                    [
                        ("c1", "id", "integer", True),
                        ("c2", "lead_id", "integer", False),
                    ],
                ),
                _make_table(
                    "t2",
                    "employee",
                    [
                        ("c3", "id", "integer", True),
                        ("c4", "project_id", "integer", False),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="project_lead",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t2",
                    targetColumnId="c4",
                    type="1:n",
                    isRequired=False,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
                RelationshipModel(
                    id="r2",
                    name="employee_lead",
                    sourceTableId="t2",
                    sourceColumnId="c3",
                    targetTableId="t1",
                    targetColumnId="c2",
                    type="1:n",
                    isRequired=False,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        assert "project" in meta["employee"].get("circular_depends_on", [])
        assert "employee" in meta["project"].get("circular_depends_on", [])
        assert "project" not in meta["employee"]["depends_on"]
        assert "employee" not in meta["project"]["depends_on"]

    def test_classifications_extracted(self):
        schema = SchemaModel(
            tables=[
                _make_table(
                    "t1",
                    "customer",
                    [
                        ("c1", "id", "integer", True),
                        ("c2", "email", "string", False),
                        ("c3", "first_name", "string", False),
                        ("c4", "last_name", "string", False),
                    ],
                ),
            ],
            relationships=[],
        )
        meta = SemanticAnalyzer.analyze(schema)
        classifications = meta["customer"]["classifications"]
        assert classifications.get("email") is not None
        assert classifications.get("first_name") is not None
        assert classifications.get("last_name") is not None


class TestDependencyGraph:
    def test_topological_ordering(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "parent", [("c1", "id", "integer", True)]),
                _make_table(
                    "t2",
                    "child",
                    [
                        ("c2", "cid", "integer", True),
                        ("c3", "parent_id", "integer", False),
                    ],
                ),
                _make_table(
                    "t3",
                    "grandchild",
                    [
                        ("c4", "gcid", "integer", True),
                        ("c5", "child_id", "integer", False),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="r1",
                    name="pc",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t2",
                    targetColumnId="c3",
                    type="1:n",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
                RelationshipModel(
                    id="r2",
                    name="cgc",
                    sourceTableId="t2",
                    sourceColumnId="c2",
                    targetTableId="t3",
                    targetColumnId="c5",
                    type="1:n",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )
        meta = SemanticAnalyzer.analyze(schema)
        graph = SemanticAnalyzer.build_dependency_graph(meta)
        ordered, groups, _ = graph.get_topological_sort_and_layers()

        p_idx = ordered.index("parent")
        c_idx = ordered.index("child")
        gc_idx = ordered.index("grandchild")
        assert p_idx < c_idx < gc_idx

    def test_independent_tables_in_same_layer(self):
        schema = SchemaModel(
            tables=[
                _make_table("t1", "a", [("c1", "id", "integer", True)]),
                _make_table("t2", "b", [("c2", "id", "integer", True)]),
            ],
            relationships=[],
        )
        meta = SemanticAnalyzer.analyze(schema)
        graph = SemanticAnalyzer.build_dependency_graph(meta)
        _, groups, _ = graph.get_topological_sort_and_layers()
        assert len(groups) == 1
        assert set(groups[0]) == {"a", "b"}
