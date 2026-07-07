import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy base class for all platform relational database tables."""

    pass


class Project(Base):
    """Workspace project entities containing dataset schema revisions."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(
        String(50), default="pending", nullable=True
    )
    # Optimistic locking version counter column
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    schemas: Mapped[list["Schema"]] = relationship(
        "Schema", back_populates="project", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(
        "Job", back_populates="project", cascade="all, delete-orphan"
    )


class Schema(Base):
    """Database structure schemas matching designer state versions."""

    __tablename__ = "schemas"
    __table_args__ = (
        # Composite index for quick active version sweeps per workspace project
        Index("idx_schema_project_active", "project_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Foreign key index for relationship lookups
    project_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    tables_json: Mapped[str] = mapped_column(Text)
    relationships_json: Mapped[str] = mapped_column(Text)
    is_active: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    project: Mapped["Project"] = relationship("Project", back_populates="schemas")
    validations: Mapped[list["ValidationHistory"]] = relationship(
        "ValidationHistory", back_populates="schema", cascade="all, delete-orphan"
    )


class Job(Base):
    """Background task validation or row generation execution log entry."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Foreign key index to speed up jobs filters
    project_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    result_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="jobs")
    export_history: Mapped[Optional["ExportHistory"]] = relationship(
        "ExportHistory", back_populates="job", cascade="all, delete-orphan"
    )
    dataset_metadata: Mapped[Optional["DatasetMetadata"]] = relationship(
        "DatasetMetadata", back_populates="job", cascade="all, delete-orphan"
    )


class ValidationHistory(Base):
    """Local schema validation runs diagnostics trail."""

    __tablename__ = "validation_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    # Foreign key lookup index
    schema_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("schemas.id", ondelete="CASCADE"), index=True
    )
    run_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    result_status: Mapped[str] = mapped_column(String(50))
    issues_json: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[float] = mapped_column(Float)

    schema: Mapped["Schema"] = relationship("Schema", back_populates="validations")


class DatasetMetadata(Base):
    """Metadata generated during row seeding tasks."""

    __tablename__ = "dataset_metadata"

    job_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    )
    total_rows: Mapped[int] = mapped_column(Integer)
    table_stats_json: Mapped[str] = mapped_column(Text)
    folder_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    job: Mapped["Job"] = relationship("Job", back_populates="dataset_metadata")


class ExportHistory(Base):
    """Log of all exported file artifacts."""

    __tablename__ = "export_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("jobs.id", ondelete="CASCADE")
    )
    format: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(255))
    checksum: Mapped[str] = mapped_column(String(64))
    file_size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    job: Mapped["Job"] = relationship("Job", back_populates="export_history")


class Issue(Base):
    """Caretaker diagnostics tickets."""

    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    category: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    detected_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    source: Mapped[str] = mapped_column(String(100))
    affected_component: Mapped[str] = mapped_column(String(255))
    suggested_fix: Mapped[str] = mapped_column(Text)

    events: Mapped[list["IssueEvent"]] = relationship(
        "IssueEvent", back_populates="issue", cascade="all, delete-orphan"
    )


class IssueEvent(Base):
    """Lifecycle events associated with Caretaker issues."""

    __tablename__ = "issue_events"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    issue_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("issues.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(100))
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    author: Mapped[str] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    issue: Mapped["Issue"] = relationship("Issue", back_populates="events")


class CaretakerHistory(Base):
    """Audit logs of caretaker daemon monitoring runs."""

    __tablename__ = "caretaker_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    run_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    checked_modules_json: Mapped[str] = mapped_column(Text)
    unhealthy_count: Mapped[int] = mapped_column(Integer)
    actions_taken: Mapped[int] = mapped_column(Integer)


class SystemMetadata(Base):
    """Platform system metadata settings."""

    __tablename__ = "system_metadata"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    platform_version: Mapped[str] = mapped_column(String(50))
    schema_version: Mapped[int] = mapped_column(Integer)
    storage_version: Mapped[int] = mapped_column(Integer)
    migration_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class AuditLog(Base):
    """Audit trail logs for tracking system events."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    component: Mapped[str] = mapped_column(String(100))
    actor: Mapped[str] = mapped_column(String(100))
    details_json: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )


class AppSetting(Base):
    """Global configuration settings key-value store."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class LLMTelemetry(Base):
    """Persistent telemetry record for every LLM gateway execution."""

    __tablename__ = "llm_telemetry"
    __table_args__ = (
        Index("idx_llm_telemetry_provider", "provider"),
        Index("idx_llm_telemetry_timestamp", "timestamp"),
        Index("idx_llm_telemetry_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
