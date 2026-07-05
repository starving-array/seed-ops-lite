"""Core data models representing memory entries, snapshots, queries, and contexts for AI Agents."""

import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    """Supported memory tiers and classifications."""

    WORKING = "working"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SHARED = "shared"
    SYSTEM = "system"


class MemoryEntry(BaseModel):
    """Single key-value entry stored inside agent memory."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="Unique entry identifier.")
    workflow_id: str = Field(..., description="Associated workflow ID.")
    execution_id: str = Field(..., description="Associated execution ID.")
    agent_id: str = Field(..., description="Owner agent ID.")
    session_id: str = Field(..., description="Optional user/system session ID.")
    memory_type: MemoryType = Field(..., description="Memory classification tier.")
    key: str = Field(..., description="Lookup dictionary key.")
    value: str = Field(..., description="Authoritative JSON payload value.")
    created_time: float = Field(
        default_factory=time.time, description="Creation timestamp."
    )
    updated_time: float = Field(
        default_factory=time.time, description="Last update timestamp."
    )
    expire_time: float | None = Field(
        default=None, description="Optional epoch expiration TTL."
    )


class AgentMemory(BaseModel):
    """Isolated memory partition workspace for a concrete agent execution."""

    model_config = ConfigDict(frozen=True)

    agent_id: str
    workflow_id: str
    execution_id: str
    session_id: str
    entries: list[MemoryEntry] = Field(default_factory=list)


class MemorySnapshot(BaseModel):
    """Captured frozen state of an agent's memory for persistence and restore operations."""

    model_config = ConfigDict(frozen=True)

    snapshot_id: str = Field(..., description="Unique snapshot UUID.")
    agent_id: str
    workflow_id: str
    execution_id: str
    session_id: str
    timestamp: float = Field(default_factory=time.time)
    entries: list[MemoryEntry] = Field(
        ..., description="Flat list of captured entries."
    )


class MemoryQuery(BaseModel):
    """Filter specifications for searching memory databases."""

    model_config = ConfigDict(frozen=True)

    memory_type: MemoryType | None = None
    key_prefix: str | None = None
    search_query: str | None = None
    include_expired: bool = False


class MemoryResult(BaseModel):
    """Query result response containing matching entries."""

    model_config = ConfigDict(frozen=True)

    matches: list[MemoryEntry] = Field(default_factory=list)
    query_duration_ms: float = Field(..., description="Search latency in milliseconds.")


class MemoryMetadata(BaseModel):
    """Metadata counters tracking memory tier sizes and limits."""

    model_config = ConfigDict(frozen=True)

    total_entries: int
    working_entries: int
    short_term_entries: int
    long_term_entries: int
    shared_entries: int
    system_entries: int
    oldest_entry_time: float | None = None
    newest_entry_time: float | None = None


class MemoryContext(BaseModel):
    """Consolidated execution context incorporating variables, outputs, and agent memory states."""

    model_config = ConfigDict(frozen=True)

    workflow_id: str
    execution_id: str
    workflow_version: str
    variables: dict[str, Any] = Field(default_factory=dict)
    step_outputs: dict[str, Any] = Field(default_factory=dict)
    agent_memory: AgentMemory
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)
    checkpoint_references: list[str] = Field(default_factory=list)
