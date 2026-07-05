"""AgentMemoryManager orchestrating isolation, caching policies, CRUD, snapshots, and metrics."""

import asyncio
import hashlib
import json
import time
import uuid
from typing import Any

from app.agents.memory.models import (
    MemoryEntry,
    MemoryMetadata,
    MemoryQuery,
    MemorySnapshot,
    MemoryType,
)
from app.agents.memory.sqlite_provider import SQLiteMemoryProvider
from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.runtime.manager import RuntimeManager
from app.telemetry.events import EventID


class AgentMemoryManager:
    """Orchestrates isolation scopes, validation policies, caching, and database syncs."""

    def __init__(
        self,
        db_provider: SQLiteMemoryProvider | None = None,
        cache_manager: RuntimeManager | None = None,
        max_entries: int = 1000,
    ) -> None:
        self.db = db_provider or SQLiteMemoryProvider()
        self.cache = cache_manager or RuntimeManager()
        self.max_entries = max_entries
        self._background_tasks: set[asyncio.Task[Any]] = set()

        # Metrics telemetry dictionary
        self._metrics = {
            "memory_reads": 0,
            "memory_writes": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "snapshots_created": 0,
            "restores": 0,
            "total_read_time": 0.0,
            "total_write_time": 0.0,
        }

    async def initialize(self) -> None:
        """Initialize the underlying SQLite schemas and connection pools."""
        await self.db.initialize()
        await self.cache.initialize()

    def _get_cache_key(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> str:
        raw = f"{workflow_id}:{execution_id}:{agent_id}:{session_id}:{memory_type.value}:{key}"
        return f"agent_memory:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    def get_metrics(self) -> dict[str, Any]:
        """Fetch consolidated execution metrics copy.

        Returns:
            Dict[str, Any]: Metrics metrics count.
        """
        metrics = dict(self._metrics)
        # Add derived averages
        reads = metrics["memory_reads"]
        writes = metrics["memory_writes"]
        metrics["avg_read_time_ms"] = (
            round((metrics["total_read_time"] / reads) * 1000.0, 2)
            if reads > 0
            else 0.0
        )
        metrics["avg_write_time_ms"] = (
            round((metrics["total_write_time"] / writes) * 1000.0, 2)
            if writes > 0
            else 0.0
        )
        return metrics

    async def write(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> MemoryEntry:
        """Authoritative write to SQLite first, then cache asynchronously in Redis.

        Enforces isolation boundaries, item size limits, and evicts entries on overflow.
        """
        start = time.perf_counter()
        self._metrics["memory_writes"] += 1

        # Enforce size limits and clean expired entries
        await self.db.clear_expired(time.time())

        # Check entry counts to prevent cache exhaustions
        existing_all = await self.db.query_entries(
            workflow_id, execution_id, agent_id, session_id, MemoryQuery()
        )
        if len(existing_all) >= self.max_entries:
            # FIFO eviction strategy: delete the oldest updated entry
            sorted_entries = sorted(existing_all, key=lambda e: e.updated_time)
            oldest = sorted_entries[0]
            await self.db.delete_entry(
                oldest.workflow_id,
                oldest.execution_id,
                oldest.agent_id,
                oldest.session_id,
                oldest.memory_type,
                oldest.key,
            )
            # Remove from Redis cache too
            ckey = self._get_cache_key(
                oldest.workflow_id,
                oldest.execution_id,
                oldest.agent_id,
                oldest.session_id,
                oldest.memory_type,
                oldest.key,
            )
            await self.cache.delete(ckey)

        # Generate unique entry ID
        raw_id = f"{workflow_id}:{execution_id}:{agent_id}:{session_id}:{memory_type.value}:{key}"
        entry_id = f"mem-{hashlib.sha256(raw_id.encode('utf-8')).hexdigest()}"
        val_str = json.dumps(value)
        expire_time = (
            time.time() + ttl_seconds
            if ttl_seconds is not None
            else (time.time() + platform_settings.RUNTIME_CACHE_DEFAULT_TTL_SECONDS)
        )

        entry = MemoryEntry(
            id=entry_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            agent_id=agent_id,
            session_id=session_id,
            memory_type=memory_type,
            key=key,
            value=val_str,
            expire_time=expire_time,
        )

        # Write SQLite first
        await self.db.write_entry(entry)

        # Cache asynchronously in Redis
        ckey = self._get_cache_key(
            workflow_id, execution_id, agent_id, session_id, memory_type, key
        )
        task = asyncio.create_task(
            self.cache.set(ckey, val_str, int(expire_time - time.time()))
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        logger.info(
            EventID.LOG_INFO,
            (
                "Memory Created"
                if not any(
                    e.key == key and e.memory_type == memory_type for e in existing_all
                )
                else "Memory Updated"
            ),
            component="AgentMemoryManager",
            agent_id=agent_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            memory_type=memory_type.value,
        )

        self._metrics["total_write_time"] += time.perf_counter() - start
        return entry

    async def read(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> Any | None:
        """Fetch memory entry. Checks Redis first (cache hit), falling back to SQLite on miss."""
        start = time.perf_counter()
        self._metrics["memory_reads"] += 1

        ckey = self._get_cache_key(
            workflow_id, execution_id, agent_id, session_id, memory_type, key
        )
        # Check cache
        try:
            cached = await self.cache.get(ckey)
            if cached is not None:
                self._metrics["cache_hits"] += 1
                self._metrics["total_read_time"] += time.perf_counter() - start
                return json.loads(cached)
        except Exception as exc:
            logger.debug(EventID.LOG_INFO, f"Transient cache read exception: {exc}")

        self._metrics["cache_misses"] += 1

        # Read DB
        entry = await self.db.read_entry(
            workflow_id, execution_id, agent_id, session_id, memory_type, key
        )
        if entry is None or (
            entry.expire_time is not None and entry.expire_time < time.time()
        ):
            self._metrics["total_read_time"] += time.perf_counter() - start
            return None

        # Re-populate cache asynchronously
        ttl = int(entry.expire_time - time.time()) if entry.expire_time else 3600
        if ttl > 0:
            task = asyncio.create_task(self.cache.set(ckey, entry.value, ttl))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        self._metrics["total_read_time"] += time.perf_counter() - start
        return json.loads(entry.value)

    async def delete(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> None:
        """Remove memory entry from SQLite and Redis cache."""
        await self.db.delete_entry(
            workflow_id, execution_id, agent_id, session_id, memory_type, key
        )
        ckey = self._get_cache_key(
            workflow_id, execution_id, agent_id, session_id, memory_type, key
        )
        await self.cache.delete(ckey)

    async def create_snapshot(
        self, workflow_id: str, execution_id: str, agent_id: str, session_id: str
    ) -> MemorySnapshot:
        """Freeze and capture all active entries for an agent workspace."""
        self._metrics["snapshots_created"] += 1
        entries = await self.db.query_entries(
            workflow_id, execution_id, agent_id, session_id, MemoryQuery()
        )
        # Filter expired entries
        now = time.time()
        active = [e for e in entries if e.expire_time is None or e.expire_time > now]

        snapshot_id = f"snap-{uuid.uuid4()}"
        snapshot = MemorySnapshot(
            snapshot_id=snapshot_id,
            agent_id=agent_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            session_id=session_id,
            entries=active,
        )

        logger.info(
            EventID.LOG_INFO,
            "Snapshot Created",
            component="AgentMemoryManager",
            agent_id=agent_id,
            snapshot_id=snapshot_id,
        )
        return snapshot

    async def restore_snapshot(self, snapshot: MemorySnapshot) -> None:
        """Overwrite the current agent workspace entries using a snapshot."""
        self._metrics["restores"] += 1

        # Delete existing entries in SQLite/Redis first
        existing = await self.db.query_entries(
            snapshot.workflow_id,
            snapshot.execution_id,
            snapshot.agent_id,
            snapshot.session_id,
            MemoryQuery(),
        )
        for old in existing:
            await self.delete(
                old.workflow_id,
                old.execution_id,
                old.agent_id,
                old.session_id,
                old.memory_type,
                old.key,
            )

        # Restore new snapshot entries
        for entry in snapshot.entries:
            await self.db.write_entry(entry)
            ckey = self._get_cache_key(
                entry.workflow_id,
                entry.execution_id,
                entry.agent_id,
                entry.session_id,
                entry.memory_type,
                entry.key,
            )
            # Rehydrate cache asynchronously
            ttl = int(entry.expire_time - time.time()) if entry.expire_time else 3600
            if ttl > 0:
                task = asyncio.create_task(self.cache.set(ckey, entry.value, ttl))
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)

        logger.info(
            EventID.LOG_INFO,
            "Snapshot Restored",
            component="AgentMemoryManager",
            agent_id=snapshot.agent_id,
            snapshot_id=snapshot.snapshot_id,
        )

    async def get_metadata(
        self, workflow_id: str, execution_id: str, agent_id: str, session_id: str
    ) -> MemoryMetadata:
        """Compile counts and stats detailing active registry sizes."""
        entries = await self.db.query_entries(
            workflow_id, execution_id, agent_id, session_id, MemoryQuery()
        )
        now = time.time()
        active = [e for e in entries if e.expire_time is None or e.expire_time > now]

        creation_times = [e.created_time for e in active]
        min_time = min(creation_times) if creation_times else None
        max_time = max(creation_times) if creation_times else None

        return MemoryMetadata(
            total_entries=len(active),
            working_entries=len(
                [e for e in active if e.memory_type == MemoryType.WORKING]
            ),
            short_term_entries=len(
                [e for e in active if e.memory_type == MemoryType.SHORT_TERM]
            ),
            long_term_entries=len(
                [e for e in active if e.memory_type == MemoryType.LONG_TERM]
            ),
            shared_entries=len(
                [e for e in active if e.memory_type == MemoryType.SHARED]
            ),
            system_entries=len(
                [e for e in active if e.memory_type == MemoryType.SYSTEM]
            ),
            oldest_entry_time=min_time,
            newest_entry_time=max_time,
        )
