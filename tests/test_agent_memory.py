"""Unit and integration tests for Agent Memory & Context Management."""

import asyncio
from collections.abc import AsyncGenerator

import pytest

from app.agents.memory.manager import AgentMemoryManager
from app.agents.memory.models import MemoryType


@pytest.fixture
async def memory_manager() -> AsyncGenerator[AgentMemoryManager, None]:
    """Fixture initializing temporary SQLite memory manager."""
    # Use standard test db configuration from sqlite_db_manager
    manager = AgentMemoryManager(max_entries=5)
    await manager.initialize()
    yield manager
    await manager.cache.close()


@pytest.mark.asyncio
async def test_memory_crud_operations(memory_manager: AgentMemoryManager) -> None:
    """Verify basic Create, Read, Update, Delete workflow cycles."""
    # 1. Write working memory
    await memory_manager.write(
        workflow_id="wf-1",
        execution_id="exec-1",
        agent_id="agent-x",
        session_id="sess-1",
        memory_type=MemoryType.WORKING,
        key="username",
        value="john_doe",
    )

    # 2. Read working memory
    val = await memory_manager.read(
        workflow_id="wf-1",
        execution_id="exec-1",
        agent_id="agent-x",
        session_id="sess-1",
        memory_type=MemoryType.WORKING,
        key="username",
    )
    assert val == "john_doe"

    # 3. Update entry
    await memory_manager.write(
        workflow_id="wf-1",
        execution_id="exec-1",
        agent_id="agent-x",
        session_id="sess-1",
        memory_type=MemoryType.WORKING,
        key="username",
        value="jane_doe",
    )
    val_updated = await memory_manager.read(
        workflow_id="wf-1",
        execution_id="exec-1",
        agent_id="agent-x",
        session_id="sess-1",
        memory_type=MemoryType.WORKING,
        key="username",
    )
    assert val_updated == "jane_doe"

    # 4. Delete entry
    await memory_manager.delete(
        workflow_id="wf-1",
        execution_id="exec-1",
        agent_id="agent-x",
        session_id="sess-1",
        memory_type=MemoryType.WORKING,
        key="username",
    )
    val_deleted = await memory_manager.read(
        workflow_id="wf-1",
        execution_id="exec-1",
        agent_id="agent-x",
        session_id="sess-1",
        memory_type=MemoryType.WORKING,
        key="username",
    )
    assert val_deleted is None


@pytest.mark.asyncio
async def test_memory_isolation_scopes(memory_manager: AgentMemoryManager) -> None:
    """Verify isolation boundaries prevent data leaking between scopes."""
    # Write to scope A
    await memory_manager.write(
        workflow_id="wf-a",
        execution_id="exec-a",
        agent_id="agent-a",
        session_id="sess-a",
        memory_type=MemoryType.WORKING,
        key="scoped_key",
        value="data-a",
    )

    # Write to scope B
    await memory_manager.write(
        workflow_id="wf-b",
        execution_id="exec-b",
        agent_id="agent-b",
        session_id="sess-b",
        memory_type=MemoryType.WORKING,
        key="scoped_key",
        value="data-b",
    )

    # Read scope A
    val_a = await memory_manager.read(
        workflow_id="wf-a",
        execution_id="exec-a",
        agent_id="agent-a",
        session_id="sess-a",
        memory_type=MemoryType.WORKING,
        key="scoped_key",
    )
    assert val_a == "data-a"

    # Read scope B
    val_b = await memory_manager.read(
        workflow_id="wf-b",
        execution_id="exec-b",
        agent_id="agent-b",
        session_id="sess-b",
        memory_type=MemoryType.WORKING,
        key="scoped_key",
    )
    assert val_b == "data-b"


@pytest.mark.asyncio
async def test_memory_snapshot_and_restore(memory_manager: AgentMemoryManager) -> None:
    """Verify snapshots capture state accurately and restore wipes current data."""
    await memory_manager.write(
        workflow_id="wf-snap",
        execution_id="exec-snap",
        agent_id="agent-snap",
        session_id="sess-snap",
        memory_type=MemoryType.WORKING,
        key="var_1",
        value="val_1",
    )

    # Create Snapshot
    snapshot = await memory_manager.create_snapshot(
        workflow_id="wf-snap",
        execution_id="exec-snap",
        agent_id="agent-snap",
        session_id="sess-snap",
    )
    assert len(snapshot.entries) == 1
    assert snapshot.entries[0].key == "var_1"

    # Change value to simulate drift
    await memory_manager.write(
        workflow_id="wf-snap",
        execution_id="exec-snap",
        agent_id="agent-snap",
        session_id="sess-snap",
        memory_type=MemoryType.WORKING,
        key="var_1",
        value="drifted_val",
    )

    # Restore snapshot
    await memory_manager.restore_snapshot(snapshot)

    # Verify value restored
    restored_val = await memory_manager.read(
        workflow_id="wf-snap",
        execution_id="exec-snap",
        agent_id="agent-snap",
        session_id="sess-snap",
        memory_type=MemoryType.WORKING,
        key="var_1",
    )
    assert restored_val == "val_1"


@pytest.mark.asyncio
async def test_memory_ttl_expiration(memory_manager: AgentMemoryManager) -> None:
    """Verify expired memory entries are omitted from reads."""
    await memory_manager.write(
        workflow_id="wf-ttl",
        execution_id="exec-ttl",
        agent_id="agent-ttl",
        session_id="sess-ttl",
        memory_type=MemoryType.WORKING,
        key="temp_key",
        value="expiring_data",
        ttl_seconds=-10,  # Pre-expired
    )

    val = await memory_manager.read(
        workflow_id="wf-ttl",
        execution_id="exec-ttl",
        agent_id="agent-ttl",
        session_id="sess-ttl",
        memory_type=MemoryType.WORKING,
        key="temp_key",
    )
    assert val is None


@pytest.mark.asyncio
async def test_cache_hits_and_misses_metrics(
    memory_manager: AgentMemoryManager,
) -> None:
    """Verify cache status tracks hits and misses properly."""
    from unittest.mock import patch

    cache_store: dict[str, str] = {}

    async def mock_get(key: str) -> str | None:
        return cache_store.get(key)

    async def mock_set(key: str, value: str, _expire: int | None = None) -> None:
        cache_store[key] = value

    async def mock_delete(*keys: str) -> None:
        for k in keys:
            cache_store.pop(k, None)

    with (
        patch.object(memory_manager.cache, "get", side_effect=mock_get),
        patch.object(memory_manager.cache, "set", side_effect=mock_set),
        patch.object(memory_manager.cache, "delete", side_effect=mock_delete),
    ):
        # Write entry (Populates cache asynchronously)
        await memory_manager.write(
            workflow_id="wf-metrics",
            execution_id="exec-metrics",
            agent_id="agent-metrics",
            session_id="sess-metrics",
            memory_type=MemoryType.WORKING,
            key="mkey",
            value="mval",
        )

        # Allow time for async cache set task
        await asyncio.sleep(0.05)

        # First read (Cache Hit)
        val1 = await memory_manager.read(
            workflow_id="wf-metrics",
            execution_id="exec-metrics",
            agent_id="agent-metrics",
            session_id="sess-metrics",
            memory_type=MemoryType.WORKING,
            key="mkey",
        )
        assert val1 == "mval"

        # Corrupt or wipe cache manually to test Cache Miss recovery fallback to DB
        await memory_manager.cache.delete(
            memory_manager._get_cache_key(
                "wf-metrics",
                "exec-metrics",
                "agent-metrics",
                "sess-metrics",
                MemoryType.WORKING,
                "mkey",
            )
        )

        # Second read (Cache Miss, falls back to SQLite)
        val2 = await memory_manager.read(
            workflow_id="wf-metrics",
            execution_id="exec-metrics",
            agent_id="agent-metrics",
            session_id="sess-metrics",
            memory_type=MemoryType.WORKING,
            key="mkey",
        )
        assert val2 == "mval"

        metrics = memory_manager.get_metrics()
        assert metrics["memory_reads"] == 2
        assert metrics["cache_hits"] >= 1
        assert metrics["cache_misses"] >= 1
