"""Unit tests for RelationshipPlanner, SelfReferencePlanner, and DeferredReferenceResolver."""

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.seeder.relationship_planner import (
    DeferredReferenceResolver,
    RelationshipPlanner,
    SelfReferencePlanner,
)


def _make_schema(
    tables: list[TableModel],
    relationships: list[RelationshipModel],
) -> SchemaModel:
    return SchemaModel(tables=tables, relationships=relationships)


def _make_placeholders(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return data


class TestRelationshipPlanner:
    def test_1n_assignment(self):
        schema = _make_schema(
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
                        ),
                        ColumnModel(
                            id="c3",
                            name="customer_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=False,
                            defaultValue="",
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
                ),
            ],
        )

        placeholders = {
            "Customers": [
                {"_ref_id": "c1", "id": 1},
                {"_ref_id": "c2", "id": 2},
            ],
            "Orders": [
                {"_ref_id": "o1", "order_id": 101, "customer_id": None},
                {"_ref_id": "o2", "order_id": 102, "customer_id": None},
                {"_ref_id": "o3", "order_id": 103, "customer_id": None},
            ],
        }

        stats = RelationshipPlanner.plan(schema, placeholders, seed=42)

        assert stats["Customer_Orders"] == 3
        for order in placeholders["Orders"]:
            assert order["customer_id"] in (1, 2)
            assert order["customer_id"] is not None

    def test_n1_assignment(self):
        schema = _make_schema(
            tables=[
                TableModel(
                    id="t1",
                    name="Employees",
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
                            name="department_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
                TableModel(
                    id="t2",
                    name="Departments",
                    columns=[
                        ColumnModel(
                            id="c3",
                            name="dept_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="Employee_Department",
                    sourceTableId="t1",
                    sourceColumnId="c2",
                    targetTableId="t2",
                    targetColumnId="c3",
                    type="n:1",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )

        placeholders = {
            "Employees": [
                {"_ref_id": "e1", "id": 1, "department_id": None},
                {"_ref_id": "e2", "id": 2, "department_id": None},
                {"_ref_id": "e3", "id": 3, "department_id": None},
            ],
            "Departments": [
                {"_ref_id": "d1", "dept_id": 10},
                {"_ref_id": "d2", "dept_id": 20},
            ],
        }

        stats = RelationshipPlanner.plan(schema, placeholders, seed=42)

        assert stats["Employee_Department"] == 3
        for emp in placeholders["Employees"]:
            assert emp["department_id"] in (10, 20)
            assert emp["department_id"] is not None

    def test_11_assignment(self):
        schema = _make_schema(
            tables=[
                TableModel(
                    id="t1",
                    name="Users",
                    columns=[
                        ColumnModel(
                            id="c1",
                            name="user_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
                TableModel(
                    id="t2",
                    name="Profiles",
                    columns=[
                        ColumnModel(
                            id="c2",
                            name="profile_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                        ColumnModel(
                            id="c3",
                            name="user_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="User_Profile",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t2",
                    targetColumnId="c3",
                    type="1:1",
                    isRequired=True,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )

        placeholders = {
            "Users": [
                {"_ref_id": "u1", "user_id": 1},
                {"_ref_id": "u2", "user_id": 2},
            ],
            "Profiles": [
                {"_ref_id": "p1", "profile_id": 101, "user_id": None},
                {"_ref_id": "p2", "profile_id": 102, "user_id": None},
            ],
        }

        stats = RelationshipPlanner.plan(schema, placeholders, seed=42)

        assert stats["User_Profile"] == 2
        user_ids_assigned = set()
        for prof in placeholders["Profiles"]:
            assert prof["user_id"] in (1, 2)
            assert prof["user_id"] is not None
            user_ids_assigned.add(prof["user_id"])
        assert len(user_ids_assigned) == 2

    def test_mn_through_junction(self):
        schema = _make_schema(
            tables=[
                TableModel(
                    id="t1",
                    name="Students",
                    columns=[
                        ColumnModel(
                            id="c1",
                            name="student_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
                TableModel(
                    id="t2",
                    name="Courses",
                    columns=[
                        ColumnModel(
                            id="c2",
                            name="course_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
                TableModel(
                    id="t3",
                    name="Enrollments",
                    columns=[
                        ColumnModel(
                            id="c3",
                            name="student_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                        ColumnModel(
                            id="c4",
                            name="course_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="Student_Enroll",
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
                    id="rel2",
                    name="Course_Enroll",
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

        placeholders = {
            "Students": [
                {"_ref_id": "s1", "student_id": 1},
                {"_ref_id": "s2", "student_id": 2},
            ],
            "Courses": [
                {"_ref_id": "c1", "course_id": 10},
                {"_ref_id": "c2", "course_id": 20},
                {"_ref_id": "c3", "course_id": 30},
            ],
            "Enrollments": [
                {"_ref_id": "e1", "student_id": None, "course_id": None},
                {"_ref_id": "e2", "student_id": None, "course_id": None},
                {"_ref_id": "e3", "student_id": None, "course_id": None},
                {"_ref_id": "e4", "student_id": None, "course_id": None},
            ],
        }

        stats = RelationshipPlanner.plan(schema, placeholders, seed=42)

        assert stats["Student_Enroll"] == 4
        assert stats["Course_Enroll"] == 4
        for enroll in placeholders["Enrollments"]:
            assert enroll["student_id"] in (1, 2)
            assert enroll["course_id"] in (10, 20, 30)

    def test_no_null_fks_after_plan(self):
        schema = _make_schema(
            tables=[
                TableModel(
                    id="t1",
                    name="A",
                    columns=[
                        ColumnModel(
                            id="c1",
                            name="id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
                TableModel(
                    id="t2",
                    name="B",
                    columns=[
                        ColumnModel(
                            id="c2",
                            name="id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                        ColumnModel(
                            id="c3",
                            name="a_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=False,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="A_to_B",
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

        placeholders = {
            "A": [{"_ref_id": "a1", "id": 1}],
            "B": [
                {"_ref_id": "b1", "id": 101, "a_id": None},
                {"_ref_id": "b2", "id": 102, "a_id": None},
            ],
        }

        RelationshipPlanner.plan(schema, placeholders, seed=42)
        for b in placeholders["B"]:
            assert b["a_id"] is not None


class TestSelfReferencePlanner:
    def test_self_ref_hierarchy(self):
        schema = SchemaModel(
            tables=[
                TableModel(
                    id="t1",
                    name="Employees",
                    columns=[
                        ColumnModel(
                            id="c1",
                            name="emp_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                        ColumnModel(
                            id="c2",
                            name="manager_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=True,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="Employee_Manager",
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

        metadata = {
            "Employees": {
                "self_reference": True,
                "self_reference_columns": [("manager_id", "emp_id")],
            }
        }

        placeholders = {
            "Employees": [
                {"_ref_id": "e1", "emp_id": 1, "manager_id": None},
                {"_ref_id": "e2", "emp_id": 2, "manager_id": None},
                {"_ref_id": "e3", "emp_id": 3, "manager_id": None},
                {"_ref_id": "e4", "emp_id": 4, "manager_id": None},
                {"_ref_id": "e5", "emp_id": 5, "manager_id": None},
            ],
        }

        stats = SelfReferencePlanner.plan(schema, placeholders, metadata, seed=42)

        assert stats["Employee_Manager"] == 3

        roots = [r for r in placeholders["Employees"] if r["manager_id"] is None]
        non_roots = [
            r for r in placeholders["Employees"] if r["manager_id"] is not None
        ]

        assert len(roots) >= 1
        assert len(non_roots) >= 2

        for emp in placeholders["Employees"]:
            if emp["manager_id"] is not None:
                assert emp["manager_id"] != emp["emp_id"]

        assigned_managers = {
            r["manager_id"]
            for r in placeholders["Employees"]
            if r["manager_id"] is not None
        }
        all_ids = {r["emp_id"] for r in placeholders["Employees"]}
        assert assigned_managers.issubset(all_ids)

    def test_single_record_no_self_ref(self):
        schema = SchemaModel(
            tables=[
                TableModel(
                    id="t1",
                    name="Employees",
                    columns=[
                        ColumnModel(
                            id="c1",
                            name="emp_id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                        ColumnModel(
                            id="c2",
                            name="manager_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=True,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="Employee_Manager",
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

        metadata = {
            "Employees": {
                "self_reference": True,
                "self_reference_columns": [("manager_id", "emp_id")],
            }
        }

        placeholders = {
            "Employees": [{"_ref_id": "e1", "emp_id": 1, "manager_id": None}]
        }

        stats = SelfReferencePlanner.plan(schema, placeholders, metadata, seed=42)
        assert stats["Employee_Manager"] == 0
        assert placeholders["Employees"][0]["manager_id"] is None


class TestDeferredReferenceResolver:
    def test_circular_dependency_resolution(self):
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
                            id="c2",
                            name="default_team_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=True,
                            defaultValue="",
                        ),
                    ],
                ),
                TableModel(
                    id="t2",
                    name="Teams",
                    columns=[
                        ColumnModel(
                            id="c3",
                            name="id",
                            type="integer",
                            isPrimaryKey=True,
                            isNullable=False,
                            defaultValue="",
                        ),
                        ColumnModel(
                            id="c4",
                            name="owner_id",
                            type="integer",
                            isPrimaryKey=False,
                            isNullable=True,
                            defaultValue="",
                        ),
                    ],
                ),
            ],
            relationships=[
                RelationshipModel(
                    id="rel1",
                    name="Users_DefaultTeam",
                    sourceTableId="t2",
                    sourceColumnId="c3",
                    targetTableId="t1",
                    targetColumnId="c2",
                    type="1:n",
                    isRequired=False,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
                RelationshipModel(
                    id="rel2",
                    name="Teams_Owner",
                    sourceTableId="t1",
                    sourceColumnId="c1",
                    targetTableId="t2",
                    targetColumnId="c4",
                    type="1:n",
                    isRequired=False,
                    cascadeDelete=False,
                    cascadeUpdate=False,
                ),
            ],
        )

        metadata = {
            "Users": {
                "circular_depends_on": ["Teams"],
                "depends_on": [],
            },
            "Teams": {
                "circular_depends_on": ["Users"],
                "depends_on": [],
            },
        }

        placeholders = {
            "Users": [
                {"_ref_id": "u1", "id": 1, "default_team_id": None},
                {"_ref_id": "u2", "id": 2, "default_team_id": None},
            ],
            "Teams": [
                {"_ref_id": "t1", "id": 10, "owner_id": None},
                {"_ref_id": "t2", "id": 20, "owner_id": None},
            ],
        }

        stats = DeferredReferenceResolver.resolve(
            schema, placeholders, metadata, seed=42
        )

        assert "Users_DefaultTeam" in stats
        assert "Teams_Owner" in stats
        assert stats["Users_DefaultTeam"] == 2
        assert stats["Teams_Owner"] == 2

        for user in placeholders["Users"]:
            assert user["default_team_id"] in (10, 20)
        for team in placeholders["Teams"]:
            assert team["owner_id"] in (1, 2)

    def test_resolve_only_circular(self):
        metadata = {
            "Customers": {"circular_depends_on": [], "depends_on": []},
            "Orders": {"circular_depends_on": [], "depends_on": ["Customers"]},
        }

        stats = DeferredReferenceResolver.resolve(
            SchemaModel(tables=[], relationships=[]),
            {},
            metadata,
            seed=42,
        )
        assert stats == {}
