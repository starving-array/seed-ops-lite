"""First-time user onboarding guided tours, progress trackers, and sample schemas."""

import time
from typing import Any

from pydantic import BaseModel, Field

from app.platform.configuration.settings import platform_settings
from app.schemas.schema_design import (
    ColumnModel,
    RelationshipModel,
    SchemaModel,
    TableModel,
)


class TourStep(BaseModel):
    """Pydantic model representing a guided tour overlay step definition."""

    step_id: str = Field(..., alias="stepId")
    title: str
    content: str
    target_element_id: str = Field(..., alias="targetElementId")
    order: int

    class Config:
        populate_by_name = True
        populate_by_alias = True


class OnboardingProgress(BaseModel):
    """Pydantic model representing current user tour completion checklist."""

    completed_step_ids: list[str] = Field(
        default_factory=list, alias="completedStepIds"
    )
    skipped_step_ids: list[str] = Field(default_factory=list, alias="skippedStepIds")
    last_viewed_step_id: str | None = Field(default=None, alias="lastViewedStepId")
    is_tour_completed: bool = Field(default=False, alias="isTourCompleted")
    has_dismissed_welcome: bool = Field(default=False, alias="hasDismissedWelcome")

    class Config:
        populate_by_name = True
        populate_by_alias = True


class OnboardingStatistics(BaseModel):
    """Pydantic model representing onboarding conversion and skip analytics."""

    tours_started: int = Field(default=0, alias="toursStarted")
    tours_completed: int = Field(default=0, alias="toursCompleted")
    tours_skipped: int = Field(default=0, alias="toursSkipped")
    average_completion_time_seconds: float = Field(
        default=0.0, alias="averageCompletionTimeSeconds"
    )
    sample_projects_created: int = Field(default=0, alias="sampleProjectsCreated")

    class Config:
        populate_by_name = True
        populate_by_alias = True


# Predefined guided tour steps
TOUR_STEPS: list[TourStep] = [
    TourStep(
        stepId="welcome",
        title="Welcome to SafeSeedOps Lite",
        content="Let's take a quick 2-minute tour to see how to design schemas and generate safe production-ready datasets.",
        targetElementId="app-welcome",
        order=1,
    ),
    TourStep(
        stepId="schema-designer",
        title="Schema Designer",
        content="Here you can create tables, configure column datatypes, and set foreign key relations.",
        targetElementId="schema-designer-container",
        order=2,
    ),
    TourStep(
        stepId="ddl-import",
        title="PostgreSQL DDL Import",
        content="Paste PostgreSQL CREATE TABLE scripts to automatically populate your diagram and schema canvas.",
        targetElementId="ddl-import-button",
        order=3,
    ),
    TourStep(
        stepId="er-diagram",
        title="Interactive ER Diagram",
        content="View tables and relationships in real time. Drag nodes or adjust layout coordinates visually.",
        targetElementId="er-diagram-container",
        order=4,
    ),
    TourStep(
        stepId="generation",
        title="Generate Data",
        content="Configure target row counts and dispatch background worker processes to fill tables with test data.",
        targetElementId="generate-dataset-panel",
        order=5,
    ),
]


class SampleProjectProvider:
    """Generates realistic relational database schemas for users to experiment with safely."""

    @staticmethod
    def get_sample_schema() -> SchemaModel:
        """Create sample containing Users, Roles, Products, Categories, Orders, and Items."""
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
                        id="email",
                        name="email",
                        type="varchar",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                    ColumnModel(
                        id="role_id",
                        name="role_id",
                        type="integer",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
            TableModel(
                id="roles",
                name="roles",
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
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
            TableModel(
                id="products",
                name="products",
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
                        isNullable=False,
                        defaultValue="",
                    ),
                    ColumnModel(
                        id="category_id",
                        name="category_id",
                        type="integer",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
            TableModel(
                id="categories",
                name="categories",
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
                        id="title",
                        name="title",
                        type="varchar",
                        isPrimaryKey=False,
                        isNullable=False,
                        defaultValue="",
                    ),
                ],
            ),
        ]

        relationships = [
            RelationshipModel(
                id="rel_users_roles",
                name="fk_users_roles",
                sourceTableId="users",
                sourceColumnId="role_id",
                targetTableId="roles",
                targetColumnId="id",
                type="ManyToOne",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
            RelationshipModel(
                id="rel_products_categories",
                name="fk_products_categories",
                sourceTableId="products",
                sourceColumnId="category_id",
                targetTableId="categories",
                targetColumnId="id",
                type="ManyToOne",
                isRequired=True,
                cascadeDelete=False,
                cascadeUpdate=False,
            ),
        ]

        return SchemaModel(tables=tables, relationships=relationships)


class ProgressTracker:
    """Manages active walkthrough step pointers, skips, and resets."""

    def __init__(self) -> None:
        self.progress = OnboardingProgress()
        self.start_time: float = 0.0

    def start_tour(self) -> None:
        """Begin tour tracker timers."""
        self.start_time = time.perf_counter()
        self.progress.is_tour_completed = False
        self.progress.completed_step_ids = []
        self.progress.skipped_step_ids = []

    def complete_step(self, step_id: str) -> None:
        """Mark a tour step completed and save last active pointer."""
        if step_id not in self.progress.completed_step_ids:
            self.progress.completed_step_ids.append(step_id)
        self.progress.last_viewed_step_id = step_id

    def skip_step(self, step_id: str) -> None:
        """Mark a tour step skipped."""
        if step_id not in self.progress.skipped_step_ids:
            self.progress.skipped_step_ids.append(step_id)
        self.progress.last_viewed_step_id = step_id


class OnboardingManager:
    """Central manager handling welcome screen, walkthrough steps, sample templates, and analytics."""

    def __init__(self) -> None:
        self.tracker = ProgressTracker()
        self.stats = OnboardingStatistics()
        self.is_auto_launch_enabled = platform_settings.PLATFORM_ONBOARDING_AUTO_LAUNCH

    def initialize_onboarding(self) -> dict[str, Any]:
        """Check preferences and generate setup overlay properties."""
        should_launch = (
            self.is_auto_launch_enabled
            and not self.tracker.progress.has_dismissed_welcome
        )
        return {
            "autoLaunch": should_launch,
            "welcomeDismissed": self.tracker.progress.has_dismissed_welcome,
        }

    def dismiss_welcome(self) -> None:
        """Save dismiss welcome preferences."""
        self.tracker.progress.has_dismissed_welcome = True

    def get_tour_steps(self) -> list[TourStep]:
        """Get the list of defined guided walkthrough steps."""
        limit = platform_settings.PLATFORM_ONBOARDING_MAX_STEPS
        return TOUR_STEPS[:limit]

    def create_sample_project(self) -> SchemaModel:
        """Generate sample schema database model."""
        self.stats.sample_projects_created += 1
        return SampleProjectProvider.get_sample_schema()

    def complete_tour(self) -> None:
        """Complete the onboarding journey and log duration metrics."""
        self.tracker.progress.is_tour_completed = True
        self.stats.tours_completed += 1
        if self.tracker.start_time > 0.0:
            duration = time.perf_counter() - self.tracker.start_time
            self.stats.average_completion_time_seconds = duration

    def skip_tour(self) -> None:
        """Skip remaining onboarding steps."""
        self.stats.tours_skipped += 1
