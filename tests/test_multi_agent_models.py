"""Unit tests verifying Multi-Agent Domain models, validations, and lifecycle states."""

import pytest
from pydantic import ValidationError

from app.agents.collaboration.models import (
    AgentMember,
    AgentRole,
    AgentTeam,
    CollaborationSession,
    CollaborationState,
    CollaborationStatistics,
    SharedContext,
)


def test_agent_role_and_lifecycle_enums() -> None:
    """Verify role classifications and session state values."""
    assert AgentRole.COORDINATOR.value == "Coordinator"
    assert AgentRole.VALIDATOR.value == "Validator"

    assert CollaborationState.CREATED.value == "Created"
    assert CollaborationState.COMPLETED.value == "Completed"


def test_agent_team_validation_and_immutability() -> None:
    """Verify unique member IDs are enforced and team models remain immutable."""
    members = [
        AgentMember(
            agent_id="agent-1", role=AgentRole.COORDINATOR, capabilities=["lead"]
        ),
        AgentMember(agent_id="agent-2", role=AgentRole.PLANNER, capabilities=["plan"]),
    ]

    team = AgentTeam(team_id="team-1", name="Alpha Team", members=members)
    assert team.team_id == "team-1"

    # Verify immutability
    with pytest.raises(ValidationError):
        # Pydantic v2 frozen models prevent attribute writes
        team.name = "Beta Team"

    # Verify duplicate member ID prevention
    duplicate_members = [
        AgentMember(agent_id="agent-1", role=AgentRole.COORDINATOR),
        AgentMember(agent_id="agent-1", role=AgentRole.PLANNER),
    ]
    with pytest.raises(ValidationError) as exc_info:
        AgentTeam(team_id="team-2", name="Broken Team", members=duplicate_members)
    assert "Duplicate team member ID detected" in str(exc_info.value)


def test_shared_context_limits_validation() -> None:
    """Verify shared variables density checks respect PlatformSettings configuration limits."""
    # Attempt to build context exceeding variables volume threshold
    variables = {f"key_{i}": f"value_{i}" for i in range(200)}
    with pytest.raises(ValidationError) as exc_info:
        SharedContext(
            workflow_id="wf-1",
            execution_id="exec-1",
            team_id="team-1",
            shared_variables=variables,
        )
    assert "Shared variables count exceeds allowed limit" in str(exc_info.value)


def test_serialization_and_deserialization_loop() -> None:
    """Verify domain models support standard JSON serialization loops."""
    members = [
        AgentMember(
            agent_id="agent-1", role=AgentRole.COORDINATOR, capabilities=["lead"]
        ),
    ]
    team = AgentTeam(team_id="team-1", name="Alpha Team", members=members)
    stats = CollaborationStatistics(agent_count=1, delegated_tasks=0)
    ctx = SharedContext(
        workflow_id="wf-1",
        execution_id="exec-1",
        team_id="team-1",
        shared_variables={"run": "active"},
        execution_statistics=stats,
    )
    session = CollaborationSession(session_id="sess-1", team=team, context=ctx)

    serialized = session.model_dump_json()
    deserialized = CollaborationSession.model_validate_json(serialized)

    assert deserialized.session_id == "sess-1"
    assert deserialized.team.team_id == "team-1"
    assert deserialized.context.workflow_id == "wf-1"
    assert deserialized.context.shared_variables["run"] == "active"
