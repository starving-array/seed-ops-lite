"""Enterprise Foundation Pydantic Models & Enums."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    """Predefined enterprise roles for access control."""

    OWNER = "Owner"
    ADMINISTRATOR = "Administrator"
    DEVELOPER = "Developer"
    OPERATOR = "Operator"
    REVIEWER = "Reviewer"
    VIEWER = "Viewer"


class Permission(str, Enum):
    """Finer-grained resource access capabilities."""

    WORKFLOW_READ = "workflow:read"
    WORKFLOW_WRITE = "workflow:write"
    EXECUTION_READ = "execution:read"
    EXECUTION_WRITE = "execution:write"
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    TOOLS_READ = "tools:read"
    TOOLS_WRITE = "tools:write"
    APPROVALS_READ = "approvals:read"
    APPROVALS_WRITE = "approvals:write"
    ADMINISTRATION = "administration"
    API_READ = "api:read"
    API_WRITE = "api:write"
    CONFIGURATION_READ = "configuration:read"
    CONFIGURATION_WRITE = "configuration:write"


class Organization(BaseModel):
    """Organization model representing the top level corporate entity."""

    model_config = ConfigDict(frozen=True)

    org_id: str
    name: str
    owner_id: str


class Project(BaseModel):
    """Project model holding workspaces and teams within an organization."""

    model_config = ConfigDict(frozen=True)

    project_id: str
    org_id: str
    name: str


class Workspace(BaseModel):
    """Workspace model representing isolated staging environments."""

    model_config = ConfigDict(frozen=True)

    workspace_id: str
    project_id: str
    name: str


class Team(BaseModel):
    """Team model grouping members within an organization."""

    model_config = ConfigDict(frozen=True)

    team_id: str
    org_id: str
    name: str
    members: list[str] = Field(default_factory=list)


class Member(BaseModel):
    """Member model detailing user role inside an organization."""

    model_config = ConfigDict(frozen=True)

    user_id: str
    email: str
    role: str


class Invitation(BaseModel):
    """Invitation model representing pending member invites."""

    model_config = ConfigDict(frozen=True)

    invitation_id: str
    org_id: str
    email: str
    role: str
    status: str = "Pending"  # Pending, Accepted, Declined


class ApiKey(BaseModel):
    """API Key model representing system credentials."""

    model_config = ConfigDict(frozen=True)

    key_id: str
    hashed_key: str
    user_id: str
    expires_at: float
    rotated_at: float | None = None


class ServiceAccount(BaseModel):
    """Service account model representing programmatic integrations."""

    model_config = ConfigDict(frozen=True)

    service_account_id: str
    name: str
    role: str
    org_id: str


class AuditLogEntry(BaseModel):
    """System audit record tracking actions, actors, and targets."""

    model_config = ConfigDict(frozen=True)

    log_id: str
    actor_id: str
    event_type: str
    details: dict[str, Any]
    timestamp: float
