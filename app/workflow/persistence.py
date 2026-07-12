"""Workflow persistence, versioning, audit trail tracking, and import/export manager."""

import json
import sqlite3
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import UTC
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging.logging import logger
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.telemetry.events import EventID
from app.workflow.dsl.models import WorkflowDefinition
from app.workflow.dsl.parser import load_from_yaml, to_yaml
from app.workflow.dsl.validator_engine import WorkflowValidator


class WorkflowLifecycleState(str, Enum):
    """Lifecycle state stages for workflow version configurations."""

    DRAFT = "Draft"
    REVIEW = "Review"
    PUBLISHED = "Published"
    DEPRECATED = "Deprecated"
    ARCHIVED = "Archived"
    DELETED = "Deleted"


class StepDiff(BaseModel):
    """Differential step differences list."""

    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)


class WorkflowDiff(BaseModel):
    """Calculated comparison diff model between two workflow versions."""

    step_changes: StepDiff = Field(default_factory=StepDiff)
    variable_changes: dict[str, str] = Field(default_factory=dict)
    metadata_changes: list[str] = Field(default_factory=list)


class AuditTrailEntry(BaseModel):
    """Audit logging structure for schema state operations."""

    timestamp: str
    event_type: str
    workflow_id: str
    workflow_version: str
    actor: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowRepository(ABC):
    """Repository boundary interface defining persistence requirements."""

    @abstractmethod
    def save(
        self, workflow: WorkflowDefinition, change_summary: str, actor: str
    ) -> None:
        """Saves a new immutable workflow definition version."""
        pass

    @abstractmethod
    def get(self, workflow_id: str, version: str) -> WorkflowDefinition | None:
        """Loads a specific workflow definition version."""
        pass

    @abstractmethod
    def get_latest(self, workflow_id: str) -> WorkflowDefinition | None:
        """Loads the latest published or draft version of a workflow."""
        pass

    @abstractmethod
    def list_workflows(self, include_deleted: bool = False) -> list[WorkflowDefinition]:
        """Lists active workflows definitions."""
        pass

    @abstractmethod
    def soft_delete(self, workflow_id: str, actor: str) -> None:
        """Flags a workflow definition as soft deleted."""
        pass

    @abstractmethod
    def restore(self, workflow_id: str, actor: str) -> None:
        """Restores a soft deleted workflow."""
        pass

    @abstractmethod
    def publish(self, workflow_id: str, version: str, actor: str) -> None:
        """Publishes a workflow definition version."""
        pass


def init_persistence_tables() -> None:
    """Initializes schema and audit logging tables in SQLite."""
    db_path = sqlite_db_manager.db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_definitions (
                workflow_id TEXT,
                version TEXT,
                name TEXT,
                description TEXT,
                status TEXT,
                definition_yaml TEXT,
                change_summary TEXT,
                created_at TEXT,
                updated_at TEXT,
                deleted INTEGER DEFAULT 0,
                PRIMARY KEY (workflow_id, version)
            )
        """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_audit_trail (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                workflow_id TEXT,
                workflow_version TEXT,
                actor TEXT,
                summary TEXT,
                metadata TEXT
            )
        """
        )
        conn.commit()
    finally:
        conn.close()


class SQLiteWorkflowRepository(WorkflowRepository):
    """Durable SQLite storage engine implementation for Workflow definitions and audit trail."""

    def __init__(self) -> None:
        init_persistence_tables()

    def save(
        self, workflow: WorkflowDefinition, change_summary: str, actor: str
    ) -> None:
        # Validate using existing validator engine first
        val_res = WorkflowValidator.validate(workflow)
        if not val_res.valid:
            errors_str = "; ".join(err.message for err in val_res.errors)
            raise ValueError(f"Workflow failed validation: {errors_str}")

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            from datetime import datetime

            now = datetime.now(UTC).isoformat() + "Z"

            # Check if this specific version already exists (version immutability rule)
            cursor.execute(
                "SELECT 1 FROM workflow_definitions WHERE workflow_id = ? AND version = ?",
                (workflow.id, workflow.workflow_version),
            )
            if cursor.fetchone():
                raise ValueError(
                    f"Workflow version {workflow.workflow_version} is immutable and cannot be overwritten."
                )

            # If status is published, mark other versions of this workflow as deprecated
            # Wait, let's keep status as tag or simple field
            status_val = (
                WorkflowLifecycleState.PUBLISHED.value
                if len(workflow.steps) > 0
                else WorkflowLifecycleState.DRAFT.value
            )

            yaml_payload = to_yaml(workflow)

            cursor.execute(
                """
                INSERT INTO workflow_definitions (
                    workflow_id, version, name, description, status, definition_yaml, change_summary, created_at, updated_at, deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
                (
                    workflow.id,
                    workflow.workflow_version,
                    workflow.name,
                    workflow.description or "",
                    status_val,
                    yaml_payload,
                    change_summary,
                    now,
                    now,
                ),
            )

            # Add audit trail entry
            cursor.execute(
                """
                INSERT INTO workflow_audit_trail (
                    timestamp, event_type, workflow_id, workflow_version, actor, summary, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    now,
                    (
                        "WorkflowCreated"
                        if workflow.workflow_version == "1.0.0"
                        else "WorkflowUpdated"
                    ),
                    workflow.id,
                    workflow.workflow_version,
                    actor,
                    f"Saved version {workflow.workflow_version}: {change_summary}",
                    json.dumps({"name": workflow.name}),
                ),
            )
            conn.commit()

            logger.info(
                EventID.LOG_INFO,
                "Workflow Created",
                details={
                    "workflow_id": workflow.id,
                    "version": workflow.workflow_version,
                },
            )
            DomainEventDispatcher.dispatch(
                "WorkflowCreated",
                {"workflow_id": workflow.id, "version": workflow.workflow_version},
            )
        finally:
            conn.close()

    def get(self, workflow_id: str, version: str) -> WorkflowDefinition | None:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT definition_yaml FROM workflow_definitions
                WHERE workflow_id = ? AND version = ? AND deleted = 0
            """,
                (workflow_id, version),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return load_from_yaml(row[0])
        finally:
            conn.close()

    def get_latest(self, workflow_id: str) -> WorkflowDefinition | None:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            # Sort version strings or use alphabetical fallback (assuming semver order)
            cursor.execute(
                """
                SELECT definition_yaml FROM workflow_definitions
                WHERE workflow_id = ? AND deleted = 0
                ORDER BY version DESC LIMIT 1
            """,
                (workflow_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return load_from_yaml(row[0])
        finally:
            conn.close()

    def list_workflows(self, include_deleted: bool = False) -> list[WorkflowDefinition]:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            query = "SELECT definition_yaml FROM workflow_definitions"
            if not include_deleted:
                query += " WHERE deleted = 0"
            cursor.execute(query)
            rows = cursor.fetchall()
            return [load_from_yaml(r[0]) for r in rows]
        finally:
            conn.close()

    def soft_delete(self, workflow_id: str, actor: str) -> None:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE workflow_definitions SET deleted = 1 WHERE workflow_id = ?",
                (workflow_id,),
            )
            from datetime import datetime

            now = datetime.now(UTC).isoformat() + "Z"
            cursor.execute(
                """
                INSERT INTO workflow_audit_trail (
                    timestamp, event_type, workflow_id, workflow_version, actor, summary, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    now,
                    "WorkflowDeleted",
                    workflow_id,
                    "latest",
                    actor,
                    "Soft deleted workflow definition.",
                    "{}",
                ),
            )
            conn.commit()

            logger.info(
                EventID.LOG_INFO,
                "Workflow Deleted",
                details={"workflow_id": workflow_id},
            )
            DomainEventDispatcher.dispatch(
                "WorkflowDeleted", {"workflow_id": workflow_id}
            )
        finally:
            conn.close()

    def restore(self, workflow_id: str, actor: str) -> None:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE workflow_definitions SET deleted = 0 WHERE workflow_id = ?",
                (workflow_id,),
            )
            from datetime import datetime

            now = datetime.now(UTC).isoformat() + "Z"
            cursor.execute(
                """
                INSERT INTO workflow_audit_trail (
                    timestamp, event_type, workflow_id, workflow_version, actor, summary, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    now,
                    "WorkflowRestored",
                    workflow_id,
                    "latest",
                    actor,
                    "Restored soft deleted workflow definition.",
                    "{}",
                ),
            )
            conn.commit()

            logger.info(
                EventID.LOG_INFO,
                "Workflow Restored",
                details={"workflow_id": workflow_id},
            )
            DomainEventDispatcher.dispatch(
                "WorkflowRestored", {"workflow_id": workflow_id}
            )
        finally:
            conn.close()

    def publish(self, workflow_id: str, version: str, actor: str) -> None:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            # Mark all other versions as Deprecated
            cursor.execute(
                "UPDATE workflow_definitions SET status = ? WHERE workflow_id = ? AND version != ?",
                (WorkflowLifecycleState.DEPRECATED.value, workflow_id, version),
            )
            # Mark current version as Published
            cursor.execute(
                "UPDATE workflow_definitions SET status = ? WHERE workflow_id = ? AND version = ?",
                (WorkflowLifecycleState.PUBLISHED.value, workflow_id, version),
            )
            from datetime import UTC, datetime

            now = datetime.now(UTC).isoformat() + "Z"
            cursor.execute(
                """
                INSERT INTO workflow_audit_trail (
                    timestamp, event_type, workflow_id, workflow_version, actor, summary, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    now,
                    "WorkflowPublished",
                    workflow_id,
                    version,
                    actor,
                    f"Published version {version}.",
                    "{}",
                ),
            )
            conn.commit()

            logger.info(
                EventID.LOG_INFO,
                "Workflow Published",
                details={"workflow_id": workflow_id, "version": version},
            )
            DomainEventDispatcher.dispatch(
                "WorkflowPublished", {"workflow_id": workflow_id, "version": version}
            )
        finally:
            conn.close()

    def get_audit_trail(self, workflow_id: str) -> list[AuditTrailEntry]:
        """Loads all audit entries recorded for a workflow ID."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, event_type, workflow_version, actor, summary, metadata
                FROM workflow_audit_trail WHERE workflow_id = ? ORDER BY timestamp DESC
            """,
                (workflow_id,),
            )
            rows = cursor.fetchall()
            return [
                AuditTrailEntry(
                    timestamp=r[0],
                    event_type=r[1],
                    workflow_id=workflow_id,
                    workflow_version=r[2],
                    actor=r[3],
                    summary=r[4],
                    metadata=json.loads(r[5]),
                )
                for r in rows
            ]
        finally:
            conn.close()


class WorkflowDiffEngine:
    """Compares two WorkflowDefinitions and reports added, removed, and modified elements."""

    @staticmethod
    def diff(v1: WorkflowDefinition, v2: WorkflowDefinition) -> WorkflowDiff:
        # Steps comparisons
        steps1 = {s.id: s for s in v1.steps}
        steps2 = {s.id: s for s in v2.steps}

        added_steps = [s_id for s_id in steps2 if s_id not in steps1]
        removed_steps = [s_id for s_id in steps1 if s_id not in steps2]
        modified_steps = []

        for s_id in steps2:
            if s_id in steps1:
                # Compare step definition structure/configuration
                s1_json = steps1[s_id].model_dump_json()
                s2_json = steps2[s_id].model_dump_json()
                if s1_json != s2_json:
                    modified_steps.append(s_id)

        step_changes = StepDiff(
            added=added_steps,
            removed=removed_steps,
            modified=modified_steps,
        )

        # Variable comparisons
        var_changes = {}
        for var_name in v2.variables:
            if var_name not in v1.variables:
                var_changes[var_name] = "added"
            elif v1.variables[var_name].type != v2.variables[var_name].type:
                var_changes[var_name] = "type_modified"

        for var_name in v1.variables:
            if var_name not in v2.variables:
                var_changes[var_name] = "removed"

        # Metadata changes
        meta_changes = []
        if v1.name != v2.name:
            meta_changes.append("name")
        if v1.description != v2.description:
            meta_changes.append("description")

        return WorkflowDiff(
            step_changes=step_changes,
            variable_changes=var_changes,
            metadata_changes=meta_changes,
        )
