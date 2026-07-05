"""Enterprise Platform Foundation managers implementation."""

import hashlib
import json
import sqlite3
import time
import uuid
from typing import Any

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.enterprise.models import (
    AuditLogEntry,
    Organization,
    Permission,
    Project,
    Role,
    ServiceAccount,
    Workspace,
)
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.telemetry.events import EventID

# Default Role-to-Permission mappings
ROLE_PERMISSIONS: dict[str, list[Permission]] = {
    Role.OWNER.value: list(Permission),
    Role.ADMINISTRATOR.value: [
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_WRITE,
        Permission.EXECUTION_READ,
        Permission.EXECUTION_WRITE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.TOOLS_READ,
        Permission.TOOLS_WRITE,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_WRITE,
        Permission.API_READ,
        Permission.API_WRITE,
        Permission.CONFIGURATION_READ,
        Permission.CONFIGURATION_WRITE,
    ],
    Role.DEVELOPER.value: [
        Permission.WORKFLOW_READ,
        Permission.WORKFLOW_WRITE,
        Permission.EXECUTION_READ,
        Permission.EXECUTION_WRITE,
        Permission.AGENT_READ,
        Permission.AGENT_WRITE,
        Permission.MEMORY_READ,
        Permission.MEMORY_WRITE,
        Permission.TOOLS_READ,
        Permission.TOOLS_WRITE,
        Permission.APPROVALS_READ,
        Permission.API_READ,
        Permission.CONFIGURATION_READ,
    ],
    Role.OPERATOR.value: [
        Permission.WORKFLOW_READ,
        Permission.EXECUTION_READ,
        Permission.EXECUTION_WRITE,
        Permission.AGENT_READ,
        Permission.TOOLS_READ,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_WRITE,
    ],
    Role.REVIEWER.value: [
        Permission.WORKFLOW_READ,
        Permission.EXECUTION_READ,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_WRITE,
    ],
    Role.VIEWER.value: [
        Permission.WORKFLOW_READ,
        Permission.EXECUTION_READ,
        Permission.AGENT_READ,
        Permission.TOOLS_READ,
        Permission.APPROVALS_READ,
    ],
}


def init_enterprise_tables() -> None:
    """Initialize database tables for the Enterprise Foundation module."""
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Organizations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_organizations (
                org_id TEXT PRIMARY KEY,
                name TEXT,
                owner_id TEXT
            )
            """
        )
        # Projects
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_projects (
                project_id TEXT PRIMARY KEY,
                org_id TEXT,
                name TEXT
            )
            """
        )
        # Workspaces
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_workspaces (
                workspace_id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT
            )
            """
        )
        # Members
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_members (
                user_id TEXT,
                org_id TEXT,
                email TEXT,
                role TEXT,
                PRIMARY KEY (user_id, org_id)
            )
            """
        )
        # Teams
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_teams (
                team_id TEXT PRIMARY KEY,
                org_id TEXT,
                name TEXT,
                members TEXT
            )
            """
        )
        # Invitations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_invitations (
                invitation_id TEXT PRIMARY KEY,
                org_id TEXT,
                email TEXT,
                role TEXT,
                status TEXT
            )
            """
        )
        # API Keys
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_api_keys (
                key_id TEXT PRIMARY KEY,
                hashed_key TEXT,
                user_id TEXT,
                expires_at REAL,
                rotated_at REAL
            )
            """
        )
        # Service Accounts
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_service_accounts (
                service_account_id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                org_id TEXT
            )
            """
        )
        # Audit Logs
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ent_audit_logs (
                log_id TEXT PRIMARY KEY,
                actor_id TEXT,
                event_type TEXT,
                details TEXT,
                timestamp REAL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class AuditManager:
    """Tracks authentication, authorization, execution, and configuration audits."""

    def __init__(self) -> None:
        init_enterprise_tables()

    def log_event(self, actor_id: str, event_type: str, details: dict[str, Any]) -> str:
        """Persist a new audit log record."""
        # Sanitize details (ensure no keys/secrets/passwords/comments leaked)
        sanitized_details = {}
        for k, v in details.items():
            if k.lower() in (
                "secret",
                "key",
                "password",
                "token",
                "comment",
                "credential",
            ):
                sanitized_details[k] = "[REDACTED]"
            else:
                sanitized_details[k] = v

        log_id = str(uuid.uuid4())
        timestamp = time.time()

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ent_audit_logs (log_id, actor_id, event_type, details, timestamp) VALUES (?, ?, ?, ?, ?)",
                (
                    log_id,
                    actor_id,
                    event_type,
                    json.dumps(sanitized_details),
                    timestamp,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        logger.info(
            EventID.LOG_INFO,
            f"Audit event logged: {event_type} by actor {actor_id}",
            component="AuditManager",
        )
        return log_id

    def get_logs(self, limit: int = 100) -> list[AuditLogEntry]:
        """Fetch chronological audit trail logs."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        logs = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT log_id, actor_id, event_type, details, timestamp FROM ent_audit_logs ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            for r in rows:
                logs.append(
                    AuditLogEntry(
                        log_id=r[0],
                        actor_id=r[1],
                        event_type=r[2],
                        details=json.loads(r[3]),
                        timestamp=r[4],
                    )
                )
        finally:
            conn.close()
        return logs


class OrganizationManager:
    """Manages multi-tenant organizations, invitations, and validation limits."""

    def __init__(self, audit_mgr: AuditManager | None = None) -> None:
        self.audit = audit_mgr or AuditManager()

    def create_organization(self, name: str, owner_id: str) -> Organization | None:
        """Create a new Organization checking configuration boundaries."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ent_organizations")
            if cursor.fetchone()[0] >= platform_settings.ENTERPRISE_MAX_ORGANIZATIONS:
                logger.warning(
                    EventID.LOG_WARNING,
                    "Organization creation rejected: limit exceeded.",
                    component="OrganizationManager",
                )
                return None

            org_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO ent_organizations (org_id, name, owner_id) VALUES (?, ?, ?)",
                (org_id, name, owner_id),
            )

            # Auto-join owner as OWNER member
            cursor.execute(
                "INSERT INTO ent_members (user_id, org_id, email, role) VALUES (?, ?, ?, ?)",
                (owner_id, org_id, "owner@enterprise.com", Role.OWNER.value),
            )
            conn.commit()
        finally:
            conn.close()

        org = Organization(org_id=org_id, name=name, owner_id=owner_id)
        self.audit.log_event(
            owner_id, "OrganizationCreated", {"org_id": org_id, "name": name}
        )
        return org

    def add_member(self, org_id: str, user_id: str, email: str, role: Role) -> bool:
        """Add a member user to the organization membership check max limit."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM ent_members WHERE org_id = ?", (org_id,)
            )
            if cursor.fetchone()[0] >= platform_settings.ENTERPRISE_MAX_MEMBERS:
                return False

            cursor.execute(
                "INSERT OR REPLACE INTO ent_members (user_id, org_id, email, role) VALUES (?, ?, ?, ?)",
                (user_id, org_id, email, role.value),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_member_role(self, org_id: str, user_id: str) -> str | None:
        """Fetch role of user in organization context."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role FROM ent_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()


class ProjectManager:
    """Manages projects within organizations and limits validation."""

    def __init__(self, audit_mgr: AuditManager | None = None) -> None:
        self.audit = audit_mgr or AuditManager()

    def create_project(self, org_id: str, name: str, actor_id: str) -> Project | None:
        """Generate a new project validating max settings configuration limits."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM ent_projects WHERE org_id = ?", (org_id,)
            )
            if cursor.fetchone()[0] >= platform_settings.ENTERPRISE_MAX_PROJECTS:
                return None

            project_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO ent_projects (project_id, org_id, name) VALUES (?, ?, ?)",
                (project_id, org_id, name),
            )
            conn.commit()
        finally:
            conn.close()

        p = Project(project_id=project_id, org_id=org_id, name=name)
        self.audit.log_event(
            actor_id, "ProjectCreated", {"project_id": project_id, "name": name}
        )
        return p


class WorkspaceManager:
    """Controls isolated workspaces within project scopes."""

    def __init__(self, audit_mgr: AuditManager | None = None) -> None:
        self.audit = audit_mgr or AuditManager()

    def create_workspace(self, project_id: str, name: str, actor_id: str) -> Workspace:
        """Create a workspace context."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            workspace_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO ent_workspaces (workspace_id, project_id, name) VALUES (?, ?, ?)",
                (workspace_id, project_id, name),
            )
            conn.commit()
        finally:
            conn.close()

        w = Workspace(workspace_id=workspace_id, project_id=project_id, name=name)
        self.audit.log_event(
            actor_id, "WorkspaceCreated", {"workspace_id": workspace_id, "name": name}
        )
        return w


class RoleManager:
    """Manages role specifications and custom mapping capabilities."""

    def __init__(self) -> None:
        self.custom_roles: dict[str, list[Permission]] = {}

    def define_custom_role(self, role_name: str, permissions: list[Permission]) -> None:
        """Declare a custom enterprise role mapping."""
        self.custom_roles[role_name] = permissions

    def get_role_permissions(self, role_name: str) -> list[Permission]:
        """Fetch list of permissions mapped to a role."""
        if role_name in self.custom_roles:
            return self.custom_roles[role_name]
        return ROLE_PERMISSIONS.get(role_name, [])


class PermissionEvaluator:
    """Evaluates hierarchical permissions and checks inheritance boundaries."""

    def __init__(self, org_mgr: OrganizationManager, role_mgr: RoleManager) -> None:
        self.org = org_mgr
        self.role = role_mgr

    def has_permission(
        self,
        org_id: str,
        user_id: str,
        required_permission: Permission,
    ) -> bool:
        """Verify role membership matches the required permission scope."""
        user_role = self.org.get_member_role(org_id, user_id)
        if not user_role:
            return False

        mapped_permissions = self.role.get_role_permissions(user_role)
        return required_permission in mapped_permissions


class ApiKeyManager:
    """Generates, validates, and rotates system access API keys."""

    def __init__(self, audit_mgr: AuditManager | None = None) -> None:
        self.audit = audit_mgr or AuditManager()

    def generate_api_key(self, user_id: str) -> str:
        """Create a new API key record with expiration constraints."""
        raw_key = "sk_" + str(uuid.uuid4().hex)
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        key_id = str(uuid.uuid4())
        expires_at = (
            time.time() + platform_settings.ENTERPRISE_API_KEY_EXPIRATION_SECONDS
        )

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ent_api_keys (key_id, hashed_key, user_id, expires_at, rotated_at) VALUES (?, ?, ?, ?, ?)",
                (key_id, hashed, user_id, expires_at, None),
            )
            conn.commit()
        finally:
            conn.close()

        self.audit.log_event(user_id, "ApiKeyGenerated", {"key_id": key_id})
        return raw_key

    def validate_api_key(self, raw_key: str) -> str | None:
        """Validate API key matches database entry and is not expired."""
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, expires_at FROM ent_api_keys WHERE hashed_key = ?",
                (hashed,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            user_id, expires_at = row
            if time.time() > expires_at:
                return None  # Expired

            return str(user_id)
        finally:
            conn.close()

    def rotate_api_key(self, old_raw_key: str) -> str | None:
        """Rotate existing valid api keys returning the fresh credentials."""
        user_id = self.validate_api_key(old_raw_key)
        if not user_id:
            return None

        # Revoke old key
        old_hashed = hashlib.sha256(old_raw_key.encode()).hexdigest()
        new_raw_key = self.generate_api_key(user_id)
        new_hashed = hashlib.sha256(new_raw_key.encode()).hexdigest()

        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ent_api_keys SET expires_at = 0 WHERE hashed_key = ?",
                (old_hashed,),
            )
            cursor.execute(
                "UPDATE ent_api_keys SET rotated_at = ? WHERE hashed_key = ?",
                (time.time(), new_hashed),
            )
            conn.commit()
        finally:
            conn.close()

        self.audit.log_event(user_id, "ApiKeyRotated", {})
        return new_raw_key


class ServiceAccountManager:
    """Governs service account creation and validation controls."""

    def __init__(self, audit_mgr: AuditManager | None = None) -> None:
        self.audit = audit_mgr or AuditManager()

    def create_service_account(
        self, org_id: str, name: str, role: Role, actor_id: str
    ) -> ServiceAccount:
        """Declare a service account integration credential."""
        sa_id = f"sa_{uuid.uuid4().hex[:12]}"
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ent_service_accounts (service_account_id, name, role, org_id) VALUES (?, ?, ?, ?)",
                (sa_id, name, role.value, org_id),
            )
            conn.commit()
        finally:
            conn.close()

        self.audit.log_event(
            actor_id, "ServiceAccountCreated", {"sa_id": sa_id, "name": name}
        )
        return ServiceAccount(
            service_account_id=sa_id, name=name, role=role.value, org_id=org_id
        )
