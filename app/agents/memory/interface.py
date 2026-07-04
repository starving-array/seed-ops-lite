"""Abstract interface defining required contract for Memory Providers."""

from abc import ABC, abstractmethod

from app.agents.memory.models import MemoryEntry, MemoryQuery, MemoryType


class MemoryProvider(ABC):
    """Abstract interface governing read/write operations for agent memory tiers."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection pools or schema structures."""
        pass

    @abstractmethod
    async def write_entry(self, entry: MemoryEntry) -> None:
        """Write or overwrite a memory entry.

        Args:
            entry: MemoryEntry record model.
        """
        pass

    @abstractmethod
    async def read_entry(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> MemoryEntry | None:
        """Retrieve a specific memory entry.

        Args:
            workflow_id: Scope filter.
            execution_id: Scope filter.
            agent_id: Scope filter.
            session_id: Scope filter.
            memory_type: Tier constraint.
            key: Lookup key.

        Returns:
            Optional[MemoryEntry]: The matching entry if found and unexpired, else None.
        """
        pass

    @abstractmethod
    async def delete_entry(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> None:
        """Remove a memory entry.

        Args:
            workflow_id: Scope filter.
            execution_id: Scope filter.
            agent_id: Scope filter.
            session_id: Scope filter.
            memory_type: Tier constraint.
            key: Target lookup key to delete.
        """
        pass

    @abstractmethod
    async def query_entries(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        query: MemoryQuery,
    ) -> list[MemoryEntry]:
        """Filter and retrieve memory entries matching a search criteria.

        Args:
            workflow_id: Scope filter.
            execution_id: Scope filter.
            agent_id: Scope filter.
            session_id: Scope filter.
            query: MemoryQuery filter specifications.

        Returns:
            List[MemoryEntry]: List of matching unexpired entries.
        """
        pass

    @abstractmethod
    async def clear_expired(self, current_time: float) -> int:
        """Perform database cleaning, removing expired entries.

        Args:
            current_time: Reference epoch timestamp.

        Returns:
            int: Number of deleted expired entries.
        """
        pass
