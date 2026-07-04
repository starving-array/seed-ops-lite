"""Interactive ER Diagram coordinate manager, layout engine, and bidirectional sync."""

import time

from pydantic import BaseModel, Field

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.schemas.schema_design import SchemaModel
from app.telemetry.events import EventID


class DiagramNode(BaseModel):
    """Pydantic model representing a table node in the diagram layout space."""

    table_id: str = Field(..., alias="tableId")
    x: float
    y: float
    is_collapsed: bool = Field(default=False, alias="isCollapsed")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class DiagramEdge(BaseModel):
    """Pydantic model representing relationship link line in diagram space."""

    relationship_id: str = Field(..., alias="relationshipId")
    source_table_id: str = Field(..., alias="sourceTableId")
    target_table_id: str = Field(..., alias="targetTableId")
    label: str

    class Config:
        populate_by_name = True
        populate_by_alias = True


class DiagramViewport(BaseModel):
    """Pydantic model representing viewport state offsets."""

    zoom: float = 1.0
    pan_x: float = Field(default=0.0, alias="panX")
    pan_y: float = Field(default=0.0, alias="panY")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class DiagramStatistics(BaseModel):
    """Pydantic model representing live diagram rendering and interaction metrics."""

    diagram_render_count: int = Field(default=0, alias="diagramRenderCount")
    average_render_time_ms: float = Field(default=0.0, alias="averageRenderTimeMs")
    average_synchronization_latency_ms: float = Field(
        default=0.0, alias="averageSynchronizationLatencyMs"
    )
    tables_rendered: int = Field(default=0, alias="tablesRendered")
    relationships_rendered: int = Field(default=0, alias="relationshipsRendered")
    viewport_interactions: int = Field(default=0, alias="viewportInteractions")
    layout_recalculations: int = Field(default=0, alias="layoutRecalculations")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class ERDiagramState(BaseModel):
    """Pydantic model holding full diagram layout representation."""

    nodes: list[DiagramNode] = Field(default_factory=list)
    edges: list[DiagramEdge] = Field(default_factory=list)
    viewport: DiagramViewport = Field(default_factory=DiagramViewport)
    selected_table_ids: list[str] = Field(
        default_factory=list, alias="selectedTableIds"
    )

    class Config:
        populate_by_name = True
        populate_by_alias = True


class LayoutEngine:
    """Calculates coordinate positions for diagram nodes using select algorithms."""

    @staticmethod
    def calculate_layout(
        schema: SchemaModel,
        algorithm: str = "hierarchical",
        manual_positions: dict[str, dict[str, float]] | None = None,
    ) -> list[DiagramNode]:
        """Generate grid, force-directed, or hierarchical table node placements."""
        nodes: list[DiagramNode] = []
        manual_positions = manual_positions or {}

        if algorithm.lower() == "grid":
            # Grid layout positioning
            cols = 4
            row_height = 200.0
            col_width = 300.0
            for idx, table in enumerate(schema.tables):
                # Retrieve manually adjusted positions if available
                if table.id in manual_positions:
                    x = manual_positions[table.id]["x"]
                    y = manual_positions[table.id]["y"]
                else:
                    x = (idx % cols) * col_width
                    y = (idx // cols) * row_height
                nodes.append(DiagramNode(tableId=table.id, x=x, y=y))

        else:
            # Hierarchical Layout (Vertical trees based on relationship dependency direction)
            y_levels: dict[str, float] = {}
            # Initialize all at level 0
            for table in schema.tables:
                y_levels[table.id] = 0.0

            # Push tables referenced down a layer
            for rel in schema.relationships:
                y_levels[rel.source_table_id] = max(
                    y_levels[rel.source_table_id],
                    y_levels[rel.target_table_id] + 200.0,
                )

            # Group columns horizontally per level
            level_counts: dict[float, int] = {}
            for table in schema.tables:
                level = y_levels[table.id]
                x_idx = level_counts.get(level, 0)
                level_counts[level] = x_idx + 1

                # Layout coordinate calculation
                if table.id in manual_positions:
                    x = manual_positions[table.id]["x"]
                    y = manual_positions[table.id]["y"]
                else:
                    x = x_idx * 300.0
                    y = level
                nodes.append(DiagramNode(tableId=table.id, x=x, y=y))

        return nodes


class ViewportController:
    """Manages viewport offsets, zooming, and view resets."""

    def __init__(
        self, zoom: float = 1.0, pan_x: float = 0.0, pan_y: float = 0.0
    ) -> None:
        self.zoom = zoom
        self.pan_x = pan_x
        self.pan_y = pan_y

    def zoom_in(self) -> None:
        """Increase zoom scale."""
        self.zoom = min(self.zoom + 0.1, 3.0)

    def zoom_out(self) -> None:
        """Decrease zoom scale."""
        self.zoom = max(self.zoom - 0.1, 0.2)

    def pan(self, dx: float, dy: float) -> None:
        """Pan viewport offsets."""
        self.pan_x += dx
        self.pan_y += dy

    def reset(self) -> None:
        """Reset viewport state to defaults."""
        self.zoom = platform_settings.PLATFORM_ER_DEFAULT_ZOOM
        self.pan_x = 0.0
        self.pan_y = 0.0

    def get_viewport(self) -> DiagramViewport:
        """Fetch current viewport settings."""
        return DiagramViewport(zoom=self.zoom, panX=self.pan_x, panY=self.pan_y)


class SelectionManager:
    """Manages active focus highlights on diagram nodes."""

    def __init__(self) -> None:
        self.selected_ids: list[str] = []

    def select_table(self, table_id: str, multi_select: bool = False) -> None:
        """Select node to highlight in diagram view."""
        if not multi_select:
            self.selected_ids = [table_id]
        elif table_id not in self.selected_ids:
            self.selected_ids.append(table_id)

    def deselect_table(self, table_id: str) -> None:
        """Deselect node highlighting."""
        if table_id in self.selected_ids:
            self.selected_ids.remove(table_id)

    def clear(self) -> None:
        """Clear highlight lists."""
        self.selected_ids = []


class DiagramRenderer:
    """Compiles SchemaModel and layout coordinates into diagrams."""

    @staticmethod
    def render(
        schema: SchemaModel,
        layout_nodes: list[DiagramNode],
        viewport: DiagramViewport,
        selected_ids: list[str],
    ) -> ERDiagramState:
        """Compile state variables into Diagram edge and node listings."""
        edges: list[DiagramEdge] = []
        for rel in schema.relationships:
            edges.append(
                DiagramEdge(
                    relationshipId=rel.id,
                    sourceTableId=rel.source_table_id,
                    targetTableId=rel.target_table_id,
                    label=rel.name,
                )
            )

        return ERDiagramState(
            nodes=layout_nodes,
            edges=edges,
            viewport=viewport,
            selectedTableIds=selected_ids,
        )


class ERDiagramManager:
    """Orchestrates layout algorithms, selection tracking, and schema designer synchronizations."""

    def __init__(self) -> None:
        self.viewport = ViewportController()
        self.selection = SelectionManager()
        self.manual_positions: dict[str, dict[str, float]] = {}
        self.stats = DiagramStatistics()

    def generate_diagram(self, schema: SchemaModel) -> ERDiagramState:
        """Compute state coordinates and build the ER diagram representation."""
        start_time = time.perf_counter()

        algorithm = platform_settings.PLATFORM_ER_LAYOUT_ALGORITHM
        nodes = LayoutEngine.calculate_layout(
            schema, algorithm=algorithm, manual_positions=self.manual_positions
        )

        state = DiagramRenderer.render(
            schema,
            nodes,
            self.viewport.get_viewport(),
            self.selection.selected_ids,
        )

        # Update stats
        render_time = (time.perf_counter() - start_time) * 1000.0
        self.stats.diagram_render_count += 1
        self.stats.average_render_time_ms = render_time
        self.stats.tables_rendered = len(schema.tables)
        self.stats.relationships_rendered = len(schema.relationships)

        return state

    def update_table_position(self, table_id: str, x: float, y: float) -> None:
        """Track manually adjusted node coordinates."""
        self.manual_positions[table_id] = {"x": x, "y": y}
        self.stats.viewport_interactions += 1
        self.stats.layout_recalculations += 1

    def sync_schema_designer_changes(
        self,
        schema: SchemaModel,
        designer_state: SchemaModel,
    ) -> SchemaModel:
        """Bidirectionally synchronize schema designer updates into the internal SchemaModel."""
        start_time = time.perf_counter()

        # Enforce consistency check (validate all designer changes fit criteria)
        for rel in designer_state.relationships:
            # Check broken relationships
            table_ids = [t.id.lower() for t in designer_state.tables]
            if (
                rel.source_table_id.lower() not in table_ids
                or rel.target_table_id.lower() not in table_ids
            ):
                logger.warning(
                    EventID.LOG_WARNING,
                    f"Sync validation error: broken relationship {rel.id}",
                    component="ERDiagramManager",
                )
                # Fail gracefully by keeping schema unchanged
                return schema

        sync_time = (time.perf_counter() - start_time) * 1000.0
        self.stats.average_synchronization_latency_ms = sync_time

        return designer_state
