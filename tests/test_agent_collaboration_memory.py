"""Unit and integration tests verifying Multi-Agent Shared Memory & Coordination Manager."""

import pytest

from app.agents.collaboration.memory import (
    CoordinationManager,
    SharedMemoryManager,
    SynchronizationPolicy,
)


@pytest.fixture
def memory_manager() -> SharedMemoryManager:
    return SharedMemoryManager()


@pytest.fixture
def coordination_manager(memory_manager: SharedMemoryManager) -> CoordinationManager:
    return CoordinationManager(memory_manager)


@pytest.mark.asyncio
async def test_shared_workspace_creation_and_isolation(
    memory_manager: SharedMemoryManager,
) -> None:
    """Verify that multiple workspaces are correctly isolated from each other."""
    ws1 = memory_manager.create_workspace(
        workspace_id="ws-1",
        workflow_id="wf-1",
        execution_id="exec-1",
        team_id="team-1",
        session_id="sess-1",
    )
    ws2 = memory_manager.create_workspace(
        workspace_id="ws-2",
        workflow_id="wf-2",
        execution_id="exec-2",
        team_id="team-2",
        session_id="sess-2",
    )

    assert ws1.workspace_id == "ws-1"
    assert ws2.workspace_id == "ws-2"

    memory_manager.write_variable("ws-1", "foo", "bar", "agent-1")
    memory_manager.write_variable("ws-2", "foo", "baz", "agent-2")

    assert memory_manager.read_variable("ws-1", "foo") == "bar"
    assert memory_manager.read_variable("ws-2", "foo") == "baz"


@pytest.mark.asyncio
async def test_synchronization_policy_enforcement(
    memory_manager: SharedMemoryManager,
) -> None:
    """Verify READ_ONLY and OPTIMISTIC write policy constraints."""
    memory_manager.create_workspace("ws-1", "wf-1", "exec-1", "team-1", "sess-1")

    # 1. READ_ONLY
    with pytest.raises(PermissionError):
        memory_manager.write_variable(
            "ws-1", "foo", "bar", "agent-1", policy=SynchronizationPolicy.READ_ONLY
        )

    # 2. OPTIMISTIC locking match success
    success = memory_manager.write_variable(
        "ws-1",
        "opt",
        "val1",
        "agent-1",
        policy=SynchronizationPolicy.OPTIMISTIC,
        expected_version=1,
    )
    assert success is True

    # 3. OPTIMISTIC locking mismatch failure
    failed = memory_manager.write_variable(
        "ws-1",
        "opt",
        "val2",
        "agent-1",
        policy=SynchronizationPolicy.OPTIMISTIC,
        expected_version=1,  # Version has incremented, so this should fail
    )
    assert failed is False


@pytest.mark.asyncio
async def test_snapshot_creation_and_restoration(
    memory_manager: SharedMemoryManager,
) -> None:
    """Verify that snapshots capture and restore state changes correctly."""
    memory_manager.create_workspace("ws-1", "wf-1", "exec-1", "team-1", "sess-1")
    memory_manager.write_variable("ws-1", "k1", "v1", "agent-1")

    # Take snapshot
    memory_manager.create_snapshot("ws-1", "snap-1")

    # Mutate state
    memory_manager.write_variable("ws-1", "k1", "v2", "agent-1")
    assert memory_manager.read_variable("ws-1", "k1") == "v2"

    # Restore snapshot
    success = memory_manager.restore_snapshot("ws-1", "snap-1")
    assert success is True
    assert memory_manager.read_variable("ws-1", "k1") == "v1"


@pytest.mark.asyncio
async def test_lock_handling(
    memory_manager: SharedMemoryManager, coordination_manager: CoordinationManager
) -> None:
    """Verify lock acquisition, exclusion write blocks, and release flows."""
    memory_manager.create_workspace("ws-1", "wf-1", "exec-1", "team-1", "sess-1")

    # Acquire lock on variable 'foo' for agent-1
    lock1 = await coordination_manager.acquire_lock("ws-1", "foo", "agent-1")
    assert lock1 is not None

    # Try acquiring lock on same variable for agent-2 -> Should fail
    lock2 = await coordination_manager.acquire_lock("ws-1", "foo", "agent-2")
    assert lock2 is None

    # Write to EXCLUSIVE_WRITE variable without lock -> Fails
    with pytest.raises(PermissionError):
        memory_manager.write_variable(
            "ws-1",
            "foo",
            "val",
            "agent-2",
            policy=SynchronizationPolicy.EXCLUSIVE_WRITE,
        )

    # Write to EXCLUSIVE_WRITE variable with correct lock -> Succeeds
    success = memory_manager.write_variable(
        "ws-1", "foo", "val", "agent-1", policy=SynchronizationPolicy.EXCLUSIVE_WRITE
    )
    assert success is True

    # Release lock
    released = await coordination_manager.release_lock("ws-1", "foo", "agent-1")
    assert released is True

    # Try lock acquisition again for agent-2 -> Succeeds
    lock3 = await coordination_manager.acquire_lock("ws-1", "foo", "agent-2")
    assert lock3 is not None
