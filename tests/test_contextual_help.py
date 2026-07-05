"""Unit tests for the Contextual Help and Smart Guidance engine."""

from app.platform.configuration.settings import platform_settings
from app.schemas.schema_design import ColumnModel, SchemaModel, TableModel
from app.services.contextual_help import ContextHelpManager


def test_help_configuration_loading() -> None:
    """Verify PlatformSettings help configurations loaded correctly."""
    assert platform_settings.PLATFORM_HELP_MAX_TOOLTIP_LENGTH == 500
    assert platform_settings.PLATFORM_HELP_MAX_RECOMMENDATIONS == 10
    assert platform_settings.PLATFORM_HELP_SEARCH_LIMIT == 20
    assert platform_settings.PLATFORM_HELP_CACHE_SIZE == 100


def test_tooltip_resolution_and_view_metrics() -> None:
    """Verify tooltips resolution and tracking metrics view count increment."""
    mgr = ContextHelpManager()

    # 1. Non-existent context -> returns None
    assert mgr.get_tooltip("invalid-id") is None

    # 2. Existing context -> returns Tooltip
    tooltip = mgr.get_tooltip("ddl-import")
    assert tooltip is not None
    assert tooltip.title == "DDL SQL Import"
    assert tooltip.type == "Information"

    # View metric incremented
    assert mgr.tooltips.stats.tooltip_views == 1


def test_help_search_queries() -> None:
    """Verify search index lookup matches query keywords."""
    mgr = ContextHelpManager()

    # 1. Search for primary keys
    results = mgr.search_help("primary key")
    assert len(results) > 0
    assert results[0].topic_id == "primary-keys"

    # 2. Search index keyword hits count metrics
    assert mgr.stats.help_searches == 1


def test_recommendation_evaluator() -> None:
    """Verify schema anomalies trigger smart design recommendations."""
    mgr = ContextHelpManager()

    # Define a table missing its primary key
    tables = [
        TableModel(
            id="users",
            name="users",
            columns=[
                ColumnModel(
                    id="username",
                    name="username",
                    type="varchar",
                    isPrimaryKey=False,
                    isNullable=False,
                    defaultValue="",
                ),
            ],
        ),
        TableModel(
            id="groups",
            name="groups",
            columns=[
                ColumnModel(
                    id="id",
                    name="id",
                    type="integer",
                    isPrimaryKey=True,
                    isNullable=False,
                    defaultValue="",
                ),
            ],
        ),
    ]
    schema = SchemaModel(tables=tables, relationships=[])

    recs = mgr.get_recommendations(schema)
    # 1. Should suggest missing PK for users table
    # 2. Should suggest unreferenced table warning for groups and users
    assert len(recs) == 3
    assert any(r.category == "MissingPrimaryKey" for r in recs)
    assert any(r.category == "UnreferencedTable" for r in recs)

    # Verify metrics
    assert mgr.stats.recommendations_displayed == 3
