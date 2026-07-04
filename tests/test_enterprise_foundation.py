"""Tests for the Enterprise Platform Foundation module."""

import sqlite3

import pytest

from app.platform.configuration.settings import platform_settings
from app.platform.enterprise import (
    ApiKeyManager,
    AuditManager,
    OrganizationManager,
    Permission,
    PermissionEvaluator,
    ProjectManager,
    Role,
    RoleManager,
    ServiceAccountManager,
    WorkspaceManager,
)
from app.platform.providers.sqlite_db import sqlite_db_manager


@pytest.fixture(autouse=True)
def clean_enterprise_state() -> None:
    """Fixture to ensure database is clean before running tests."""
    # Instantiating triggers table initialization
    _ = AuditManager()

    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ent_organizations")
        cursor.execute("DELETE FROM ent_projects")
        cursor.execute("DELETE FROM ent_workspaces")
        cursor.execute("DELETE FROM ent_members")
        cursor.execute("DELETE FROM ent_teams")
        cursor.execute("DELETE FROM ent_invitations")
        cursor.execute("DELETE FROM ent_api_keys")
        cursor.execute("DELETE FROM ent_service_accounts")
        cursor.execute("DELETE FROM ent_audit_logs")
        conn.commit()
    finally:
        conn.close()


def test_enterprise_configuration_loading() -> None:
    """Verify enterprise configuration values are loaded correctly from PlatformSettings."""
    assert platform_settings.ENTERPRISE_API_KEY_EXPIRATION_SECONDS == 2592000.0
    assert platform_settings.ENTERPRISE_MAX_ORGANIZATIONS == 10
    assert platform_settings.ENTERPRISE_MAX_PROJECTS == 100
    assert platform_settings.ENTERPRISE_MAX_MEMBERS == 50
    assert platform_settings.ENTERPRISE_AUDIT_RETENTION_DAYS == 90


def test_organization_crud_and_limits() -> None:
    """Verify Organization creation and maximum organization boundaries limits check."""
    audit = AuditManager()
    org_mgr = OrganizationManager(audit)

    # 1. Create organization
    org = org_mgr.create_organization("Google DeepMind", "user-123")
    assert org is not None
    assert org.name == "Google DeepMind"
    assert org.owner_id == "user-123"

    # Verify audit event logged
    logs = audit.get_logs()
    assert len(logs) == 1
    assert logs[0].event_type == "OrganizationCreated"

    # 2. Maximum limits boundary check
    # Let's adjust MAX organizations temporarily to 1 for check
    original_max = platform_settings.ENTERPRISE_MAX_ORGANIZATIONS
    platform_settings.ENTERPRISE_MAX_ORGANIZATIONS = 1
    try:
        org_limit = org_mgr.create_organization("Exceed Limit Org", "user-abc")
        assert org_limit is None
    finally:
        platform_settings.ENTERPRISE_MAX_ORGANIZATIONS = original_max


def test_project_and_workspace_isolation() -> None:
    """Verify project creation, workspaces isolation logic under projects."""
    org_mgr = OrganizationManager()
    proj_mgr = ProjectManager()
    ws_mgr = WorkspaceManager()

    org = org_mgr.create_organization("DeepMind Corp", "owner-1")
    assert org is not None

    proj = proj_mgr.create_project(org.org_id, "Project Alpha", "owner-1")
    assert proj is not None

    ws = ws_mgr.create_workspace(proj.project_id, "Staging", "owner-1")
    assert ws is not None
    assert ws.name == "Staging"
    assert ws.project_id == proj.project_id


def test_rbac_and_permission_evaluator() -> None:
    """Verify role permissions evaluation and inheritance logic."""
    org_mgr = OrganizationManager()
    role_mgr = RoleManager()
    evaluator = PermissionEvaluator(org_mgr, role_mgr)

    org = org_mgr.create_organization("Research Org", "owner-1")
    assert org is not None

    # Owner should have administration permission
    assert (
        evaluator.has_permission(org.org_id, "owner-1", Permission.ADMINISTRATION)
        is True
    )

    # Developer should not have administration permission, but should have tools:read
    org_mgr.add_member(org.org_id, "dev-1", "dev@enterprise.com", Role.DEVELOPER)
    assert (
        evaluator.has_permission(org.org_id, "dev-1", Permission.ADMINISTRATION)
        is False
    )
    assert evaluator.has_permission(org.org_id, "dev-1", Permission.TOOLS_READ) is True

    # Non-member has no permissions
    assert (
        evaluator.has_permission(org.org_id, "non-member", Permission.TOOLS_READ)
        is False
    )


def test_api_key_lifecycle() -> None:
    """Verify API Key creation, validation checks, and key rotations."""
    key_mgr = ApiKeyManager()
    user_id = "user-123"

    # 1. Generate key
    raw_key = key_mgr.generate_api_key(user_id)
    assert raw_key.startswith("sk_")

    # 2. Validate key
    validated_user = key_mgr.validate_api_key(raw_key)
    assert validated_user == user_id

    # 3. Rotate key
    new_raw_key = key_mgr.rotate_api_key(raw_key)
    assert new_raw_key is not None
    assert new_raw_key != raw_key

    # Validate old key is revoked (now invalid)
    assert key_mgr.validate_api_key(raw_key) is None

    # Validate new key works
    assert key_mgr.validate_api_key(new_raw_key) == user_id


def test_service_accounts() -> None:
    """Verify service account creation and properties."""
    sa_mgr = ServiceAccountManager()
    sa = sa_mgr.create_service_account("org-123", "Audit-Bot", Role.OPERATOR, "admin-1")
    assert sa.service_account_id.startswith("sa_")
    assert sa.name == "Audit-Bot"
    assert sa.role == Role.OPERATOR.value
    assert sa.org_id == "org-123"
