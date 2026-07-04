"""Contextual help engine, tooltips provider, and search indexing."""

from pydantic import BaseModel, Field

from app.platform.configuration.settings import platform_settings
from app.schemas.schema_design import SchemaModel


class HelpTopic(BaseModel):
    """Pydantic model representing a searchable inline documentation topic."""

    topic_id: str = Field(..., alias="topicId")
    title: str
    content: str
    keywords: list[str] = Field(default_factory=list)
    category: str

    class Config:
        populate_by_name = True
        populate_by_alias = True


class SmartRecommendation(BaseModel):
    """Pydantic model representing a suggested design enhancement recommendation."""

    recommendation_id: str = Field(..., alias="recommendationId")
    category: str
    message: str
    severity: str  # Hint, Warning, BestPractice
    suggested_action: str | None = Field(default=None, alias="suggestedAction")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class ContextTooltip(BaseModel):
    """Pydantic model representing a context-aware popup help tooltip."""

    context_id: str = Field(..., alias="contextId")
    title: str
    text: str
    type: str  # Information, Hint, Warning, BestPractice, Shortcut
    doc_link: str | None = Field(default=None, alias="docLink")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class HelpStatistics(BaseModel):
    """Pydantic model representing contextual help operational metrics."""

    tooltip_views: int = Field(default=0, alias="tooltipViews")
    help_searches: int = Field(default=0, alias="helpSearches")
    recommendations_displayed: int = Field(default=0, alias="recommendationsDisplayed")
    recommendations_accepted: int = Field(default=0, alias="recommendationsAccepted")
    validation_help_requests: int = Field(default=0, alias="validationHelpRequests")

    class Config:
        populate_by_name = True
        populate_by_alias = True


# Predefined Help Registry
HELP_REGISTRY: list[HelpTopic] = [
    HelpTopic(
        topicId="data-types",
        title="SQL Data Types",
        content="PostgreSQL data types mapped to SafeSeedOps: integer (bigint, smallint), character varying (varchar), text, boolean, numeric, timestamp.",
        keywords=["type", "varchar", "int", "boolean", "text", "numeric"],
        category="design",
    ),
    HelpTopic(
        topicId="primary-keys",
        title="Primary Keys",
        content="A primary key uniquely identifies each row in a table. It must contain unique values and cannot contain NULL values.",
        keywords=["pk", "primary", "key", "unique", "null"],
        category="design",
    ),
    HelpTopic(
        topicId="foreign-keys",
        title="Foreign Keys",
        content="A foreign key points to a primary key in another table. It establishes a referential relationship between tables.",
        keywords=["fk", "foreign", "key", "references", "relationship"],
        category="design",
    ),
]

TOOLTIP_REGISTRY: dict[str, ContextTooltip] = {
    "project-creation": ContextTooltip(
        contextId="project-creation",
        title="Create New Project",
        text="Define project name and configure base database targets to initialize isolated workspaces.",
        type="Information",
        docLink="/docs/projects",
    ),
    "ddl-import": ContextTooltip(
        contextId="ddl-import",
        title="DDL SQL Import",
        text="Paste your PostgreSQL CREATE TABLE scripts. SafeSeedOps maps columns and automatically links foreign keys.",
        type="Information",
        docLink="/docs/import",
    ),
}


class HelpSearchIndex:
    """Simple keyword matching engine for inline documentation search."""

    @staticmethod
    def search(query: str) -> list[HelpTopic]:
        """Query registry topics using keyword lookups."""
        tokens = query.lower().split()
        if not tokens:
            return []

        limit = platform_settings.PLATFORM_HELP_SEARCH_LIMIT
        scored_results: list[tuple[int, HelpTopic]] = []

        for topic in HELP_REGISTRY:
            score = 0
            title_lower = topic.title.lower()
            content_lower = topic.content.lower()

            for token in tokens:
                if token in title_lower:
                    score += 5
                if token in content_lower:
                    score += 2
                for keyword in topic.keywords:
                    if token in keyword.lower():
                        score += 3

            if score > 0:
                scored_results.append((score, topic))

        # Sort by relevance score desc
        scored_results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_results[:limit]]


class RecommendationEngine:
    """Evaluates SchemaModel structure and compiles design recommendations."""

    @staticmethod
    def evaluate_schema(schema: SchemaModel) -> list[SmartRecommendation]:
        """Find design anomalies and compile warnings (e.g. missing PKs, un-linked tables)."""
        recommendations: list[SmartRecommendation] = []
        limit = platform_settings.PLATFORM_HELP_MAX_RECOMMENDATIONS

        # 1. Check missing primary keys
        for table in schema.tables:
            has_pk = any(col.is_primary_key for col in table.columns)
            if not has_pk:
                recommendations.append(
                    SmartRecommendation(
                        recommendationId=f"rec-pk-{table.id}",
                        category="MissingPrimaryKey",
                        message=f"Table '{table.name}' does not define a primary key.",
                        severity="Warning",
                        suggestedAction=f"Define a column as isPrimaryKey=True in table '{table.name}'.",
                    )
                )

        # 2. Check tables without relationships
        table_names = [t.id for t in schema.tables]
        related_tables = set()
        for rel in schema.relationships:
            related_tables.add(rel.source_table_id)
            related_tables.add(rel.target_table_id)

        for name in table_names:
            if len(table_names) > 1 and name not in related_tables:
                recommendations.append(
                    SmartRecommendation(
                        recommendationId=f"rec-rel-{name}",
                        category="UnreferencedTable",
                        message=f"Table '{name}' is isolated and contains no relationships.",
                        severity="Hint",
                        suggestedAction=f"Define a Foreign Key referencing table '{name}' or pointed by '{name}'.",
                    )
                )

        return recommendations[:limit]


class TooltipProvider:
    """Resolves and yields tooltips by area identifiers."""

    def __init__(self) -> None:
        self.stats = HelpStatistics()

    def get_tooltip(self, context_id: str) -> ContextTooltip | None:
        """Fetch matching tooltip and increment view statistics."""
        tooltip = TOOLTIP_REGISTRY.get(context_id)
        if tooltip:
            # Check length limit
            max_len = platform_settings.PLATFORM_HELP_MAX_TOOLTIP_LENGTH
            if len(tooltip.text) > max_len:
                # Workaround to clip text
                object.__setattr__(tooltip, "text", tooltip.text[:max_len] + "...")
            self.stats.tooltip_views += 1
        return tooltip


class ContextHelpManager:
    """Central orchestrator managing search queries, recommendations, tooltips, and analytics."""

    def __init__(self) -> None:
        self.tooltips = TooltipProvider()
        self.stats = HelpStatistics()

    def get_tooltip(self, context_id: str) -> ContextTooltip | None:
        """Get contextual popup text."""
        return self.tooltips.get_tooltip(context_id)

    def get_recommendations(self, schema: SchemaModel) -> list[SmartRecommendation]:
        """Evaluate schema and compile warnings."""
        recs = RecommendationEngine.evaluate_schema(schema)
        self.stats.recommendations_displayed += len(recs)
        return recs

    def search_help(self, query: str) -> list[HelpTopic]:
        """Run search index lookups."""
        self.stats.help_searches += 1
        return HelpSearchIndex.search(query)
