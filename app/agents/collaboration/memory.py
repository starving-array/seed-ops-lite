"""Shared Memory & Multi-Agent Coordination layer."""

# ruff: noqa: RET508, RET505, S110, PLR0911

import asyncio
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging.logging import logger
from app.telemetry.events import EventID


class SynchronizationPolicy(str, Enum):
    """Synchronization concurrency policies."""

    READ_ONLY = "READ_ONLY"
    EXCLUSIVE_WRITE = "EXCLUSIVE_WRITE"
    LAST_WRITE_WINS = "LAST_WRITE_WINS"
    OPTIMISTIC = "OPTIMISTIC"
    MANUAL = "MANUAL"


class SharedLock(BaseModel):
    """Execution lock context for exclusive workspace manipulation."""

    lock_id: str = Field(..., description="Unique identifier for lock instance.")
    workspace_id: str = Field(
        ..., description="Associated workspace identification key."
    )
    acquired_by: str = Field(..., description="Agent ID holding the active lock.")
    acquired_at: float = Field(..., description="Epoch acquisition timestamp.")
    expires_at: float = Field(..., description="Lock expiration epoch time.")


class SharedSnapshot(BaseModel):
    """Workspace state dump point-in-time container."""

    snapshot_id: str = Field(..., description="Unique identification index.")
    workspace_id: str = Field(..., description="Target workspace ID.")
    version: int = Field(..., description="Snapshot sequence version index.")
    timestamp: float = Field(..., description="Epoch generation timestamp.")
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Variables values state dump."
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Intermediate outputs state dump."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata tags values."
    )


class SharedWorkspace(BaseModel):
    """Scoped workspace isolation storage context."""

    workspace_id: str = Field(..., description="Workspace ID UUID key.")
    workflow_id: str = Field(..., description="Workflow isolation context ID.")
    execution_id: str = Field(..., description="Execution path isolation identifier.")
    team_id: str = Field(..., description="Team scope key.")
    session_id: str = Field(..., description="Session boundary key.")
    tenant_id: str = Field(
        default="default", description="Tenant database separation key."
    )
    variables: dict[str, Any] = Field(
        default_factory=dict, description="Active workspace variables."
    )
    outputs: dict[str, Any] = Field(
        default_factory=dict, description="Intermediate agent outputs."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="System metadata mappings."
    )
    active_locks: dict[str, SharedLock] = Field(
        default_factory=dict, description="Current acquired locks."
    )
    version: int = Field(
        default=1, description="Concurrency state version tracking integer."
    )


class CoordinationStatistics(BaseModel):
    """Aggregated coordination metrics tracking state."""

    workspace_reads: int = 0
    workspace_writes: int = 0
    synchronization_events: int = 0
    snapshot_count: int = 0
    restore_count: int = 0
    lock_contention: int = 0
    synchronization_latency: float = 0.0
    workspace_utilization: float = 0.0


class SharedMemoryManager:
    """Manages CRUD operations on SharedWorkspaces with policy & snapshot controls."""

    def __init__(self) -> None:
        self._workspaces: dict[str, SharedWorkspace] = {}
        self._snapshots: dict[str, list[SharedSnapshot]] = {}
        self.statistics = CoordinationStatistics()

    def create_workspace(
        self,
        workspace_id: str,
        workflow_id: str,
        execution_id: str,
        team_id: str,
        session_id: str,
        tenant_id: str = "default",
    ) -> SharedWorkspace:
        """Create and register a new shared workspace scope."""
        ws = SharedWorkspace(
            workspace_id=workspace_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            team_id=team_id,
            session_id=session_id,
            tenant_id=tenant_id,
        )
        self._workspaces[workspace_id] = ws
        self._snapshots[workspace_id] = []
        logger.info(
            EventID.LOG_INFO,
            f"Workspace '{workspace_id}' created under tenant '{tenant_id}'",
            component="SharedMemoryManager",
        )
        return ws

    def get_workspace(self, workspace_id: str) -> SharedWorkspace | None:
        """Fetch workspace with existence checks."""
        self.statistics.workspace_reads += 1
        return self._workspaces.get(workspace_id)

    def write_variable(
        self,
        workspace_id: str,
        key: str,
        value: Any,
        agent_id: str,
        policy: SynchronizationPolicy = SynchronizationPolicy.LAST_WRITE_WINS,
        expected_version: int | None = None,
    ) -> bool:
        """Write a variable enforcing synchronization policies."""
        ws = self._workspaces.get(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' does not exist.")

        # 1. Enforce Max variables limit
        from app.platform.configuration.settings import platform_settings

        limit = platform_settings.MULTI_AGENT_MAX_SHARED_VARIABLES
        if len(ws.variables) >= limit and key not in ws.variables:
            raise ValueError(f"Workspace variables exceed allowed limit: {limit}")

        # 2. Enforce READ_ONLY policy
        if policy == SynchronizationPolicy.READ_ONLY:
            raise PermissionError("Cannot write to a READ_ONLY workspace.")

        # 3. Enforce EXCLUSIVE_WRITE policy (requires locked variable path)
        if policy == SynchronizationPolicy.EXCLUSIVE_WRITE:
            lock = ws.active_locks.get(key)
            if (
                not lock
                or lock.acquired_by != agent_id
                or time.time() > lock.expires_at
            ):
                raise PermissionError(
                    "EXCLUSIVE_WRITE policy requires holding an active non-expired lock."
                )

        # 4. Enforce OPTIMISTIC locking version check
        if (
            policy == SynchronizationPolicy.OPTIMISTIC
            and expected_version is not None
            and ws.version != expected_version
        ):
            self.statistics.lock_contention += 1
            return False

        # Apply update
        ws.variables[key] = value
        ws.version += 1
        self.statistics.workspace_writes += 1
        self.statistics.synchronization_events += 1

        # Track utilization metric
        self.statistics.workspace_utilization = len(ws.variables) / limit

        logger.info(
            EventID.LOG_INFO,
            f"Variable '{key}' updated in workspace '{workspace_id}'",
            component="SharedMemoryManager",
        )
        return True

    def read_variable(self, workspace_id: str, key: str) -> Any:
        """Read a variable payload safely."""
        ws = self.get_workspace(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' does not exist.")
        return ws.variables.get(key)

    def delete_variable(self, workspace_id: str, key: str) -> None:
        """Remove a variable mapping."""
        ws = self._workspaces.get(workspace_id)
        if ws and key in ws.variables:
            del ws.variables[key]
            ws.version += 1
            self.statistics.workspace_writes += 1

    def create_snapshot(
        self,
        workspace_id: str,
        snapshot_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> SharedSnapshot:
        """Dump the active workspace state to memory history logs."""
        ws = self._workspaces.get(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' does not exist.")

        from app.platform.configuration.settings import platform_settings

        max_history = platform_settings.MULTI_AGENT_MAX_SNAPSHOT_HISTORY

        # Enforce history limit
        history = self._snapshots[workspace_id]
        if len(history) >= max_history:
            history.pop(0)

        snapshot = SharedSnapshot(
            snapshot_id=snapshot_id,
            workspace_id=workspace_id,
            version=ws.version,
            timestamp=time.time(),
            variables=dict(ws.variables),
            outputs=dict(ws.outputs),
            metadata=metadata or {},
        )

        history.append(snapshot)
        self.statistics.snapshot_count += 1
        logger.info(
            EventID.LOG_INFO,
            f"Snapshot '{snapshot_id}' created for workspace '{workspace_id}'",
            component="SharedMemoryManager",
        )
        return snapshot

    def restore_snapshot(self, workspace_id: str, snapshot_id: str) -> bool:
        """Restore variables and state mappings from a prior snapshot."""
        ws = self._workspaces.get(workspace_id)
        if not ws:
            raise ValueError(f"Workspace '{workspace_id}' does not exist.")

        history = self._snapshots.get(workspace_id, [])
        target = next((s for s in history if s.snapshot_id == snapshot_id), None)
        if not target:
            return False

        ws.variables = dict(target.variables)
        ws.outputs = dict(target.outputs)
        ws.version = target.version + 1
        self.statistics.restore_count += 1

        logger.info(
            EventID.LOG_INFO,
            f"Workspace '{workspace_id}' restored to snapshot version '{target.version}'",
            component="SharedMemoryManager",
        )
        return True


class CoordinationManager:
    """Orchestrates agent state synchronization, coordination locks, and concurrency checks."""

    def __init__(self, memory_manager: SharedMemoryManager) -> None:
        self.memory_manager = memory_manager
        self._lock = asyncio.Lock()

    async def acquire_lock(
        self,
        workspace_id: str,
        key: str,
        agent_id: str,
        ttl_seconds: float = 10.0,
    ) -> SharedLock | None:
        """Attempt to acquire an exclusive write lock on a variable path key."""
        async with self._lock:
            ws = self.memory_manager.get_workspace(workspace_id)
            if not ws:
                return None

            now = time.time()
            existing = ws.active_locks.get(key)
            if existing and now < existing.expires_at:
                self.memory_manager.statistics.lock_contention += 1
                return None  # Lock is already held and not expired

            lock = SharedLock(
                lock_id=f"lock-{workspace_id}-{key}-{int(now)}",
                workspace_id=workspace_id,
                acquired_by=agent_id,
                acquired_at=now,
                expires_at=now + ttl_seconds,
            )
            ws.active_locks[key] = lock
            return lock

    async def release_lock(
        self,
        workspace_id: str,
        key: str,
        agent_id: str,
    ) -> bool:
        """Release a held lock checking ownership values."""
        async with self._lock:
            ws = self.memory_manager.get_workspace(workspace_id)
            if not ws:
                return False

            lock = ws.active_locks.get(key)
            if not lock:
                return True

            if lock.acquired_by != agent_id:
                return False  # Permission denied

            del ws.active_locks[key]
            return True
