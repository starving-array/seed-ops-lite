"""Unit tests for the ER Diagram renderer, layout engine, and synchronization."""

from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)
from app.services.er_diagram import ERDiagramManager, LayoutEngine


def get_mock_schema() -> SchemaModel:
    tables = [
        TableModel(
            id="users",
            name="users",
            columns=[
                ColumnModel(
                    id="id",
                    name="id",
                    type="integer",
                    isPrimaryKey=True,
                    isNullable=False,
                    defaultValue="",
                ),
                ColumnModel(
                    id="name",
                    name="name",
                    type="varchar",
                    isPrimaryKey=False,
                    isNullable=True,
                    defaultValue="",
                ),
            ],
        ),
        TableModel(
            id="posts",
            name="posts",
            columns=[
                ColumnModel(
                    id="id",
                    name="id",
                    type="integer",
                    isPrimaryKey=True,
                    isNullable=False,
                    defaultValue="",
                ),
                ColumnModel(
                    id="author_id",
                    name="author_id",
                    type="integer",
                    isPrimaryKey=False,
                    isNullable=False,
                    defaultValue="",
                ),
            ],
        ),
    ]
    relationships = [
        RelationshipModel(
            id="rel-1",
            name="fk_posts_author",
            sourceTableId="posts",
            sourceColumnId="author_id",
            targetTableId="users",
            targetColumnId="id",
            type="ManyToOne",
            isRequired=True,
            cascadeDelete=False,
            cascadeUpdate=False,
        )
    ]
    return SchemaModel(tables=tables, relationships=relationships)


def test_diagram_rendering_and_stats() -> None:
    """Verify diagram generates layout nodes, edges, and logs metrics."""
    schema = get_mock_schema()
    mgr = ERDiagramManager()

    state = mgr.generate_diagram(schema)
    assert len(state.nodes) == 2
    assert len(state.edges) == 1
    assert state.edges[0].source_table_id == "posts"
    assert state.edges[0].target_table_id == "users"

    # Verify rendering statistics updated
    assert mgr.stats.diagram_render_count == 1
    assert mgr.stats.tables_rendered == 2
    assert mgr.stats.relationships_rendered == 1


def test_grid_layout_nodes() -> None:
    """Verify grid layout algorithm placings."""
    schema = get_mock_schema()
    nodes = LayoutEngine.calculate_layout(schema, algorithm="grid")

    # Grid coordinates spacing validation
    assert nodes[0].x == 0.0
    assert nodes[0].y == 0.0
    assert nodes[1].x == 300.0
    assert nodes[1].y == 0.0


def test_zoom_and_viewport_navigation() -> None:
    """Verify panning, zoom, and viewport resets."""
    mgr = ERDiagramManager()

    mgr.viewport.zoom_in()
    assert mgr.viewport.zoom == 1.1

    mgr.viewport.pan(100.0, -50.0)
    assert mgr.viewport.pan_x == 100.0
    assert mgr.viewport.pan_y == -50.0

    mgr.viewport.reset()
    assert mgr.viewport.zoom == 1.0
    assert mgr.viewport.pan_x == 0.0
    assert mgr.viewport.pan_y == 0.0


def test_bidirectional_synchronization_validation() -> None:
    """Verify designer changes synchronizer sync and fail gracefully on broken relationships."""
    schema = get_mock_schema()
    mgr = ERDiagramManager()

    # 1. Successful Sync
    designer_state = get_mock_schema()
    res = mgr.sync_schema_designer_changes(schema, designer_state)
    assert res == designer_state

    # 2. Sync Rejection on Broken Relationship references
    broken_state = get_mock_schema()
    broken_state.relationships[0].target_table_id = "non-existent"

    res_broken = mgr.sync_schema_designer_changes(schema, broken_state)
    # Returns original schema to fail gracefully
    assert res_broken == schema


def test_manual_position_persistence() -> None:
    """Verify manual drag coordinates are remembered by LayoutEngine."""
    schema = get_mock_schema()
    mgr = ERDiagramManager()

    mgr.update_table_position("users", 150.0, 250.0)

    state = mgr.generate_diagram(schema)
    node_users = next(n for n in state.nodes if n.table_id == "users")
    assert node_users.x == 150.0
    assert node_users.y == 250.0
