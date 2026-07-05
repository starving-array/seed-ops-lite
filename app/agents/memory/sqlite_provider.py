"""SQLite implementation of the Agent Memory persistence provider."""

import sqlite3
from typing import Any

from app.agents.memory.interface import MemoryProvider
from app.agents.memory.models import MemoryEntry, MemoryQuery, MemoryType
from app.platform.providers.sqlite_db import sqlite_db_manager


class SQLiteMemoryProvider(MemoryProvider):
    """Authoritative memory persistence provider writing memory entries to SQLite."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or sqlite_db_manager.db_path

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    async def initialize(self) -> None:
        """Create the agent memory storage schema dynamically if it does not exist."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory_entries (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    execution_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_time REAL NOT NULL,
                    updated_time REAL NOT NULL,
                    expire_time REAL
                )
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_memory_lookup
                ON agent_memory_entries(workflow_id, execution_id, agent_id, session_id, memory_type, key)
            """
            )
            conn.commit()
        finally:
            conn.close()

    async def write_entry(self, entry: MemoryEntry) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO agent_memory_entries (
                    id, workflow_id, execution_id, agent_id, session_id, memory_type, key, value, created_time, updated_time, expire_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    value = excluded.value,
                    updated_time = excluded.updated_time,
                    expire_time = excluded.expire_time
            """,
                (
                    entry.id,
                    entry.workflow_id,
                    entry.execution_id,
                    entry.agent_id,
                    entry.session_id,
                    entry.memory_type.value,
                    entry.key,
                    entry.value,
                    entry.created_time,
                    entry.updated_time,
                    entry.expire_time,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def read_entry(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> MemoryEntry | None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, workflow_id, execution_id, agent_id, session_id, memory_type, key, value, created_time, updated_time, expire_time
                FROM agent_memory_entries
                WHERE workflow_id = ? AND execution_id = ? AND agent_id = ? AND session_id = ? AND memory_type = ? AND key = ?
            """,
                (
                    workflow_id,
                    execution_id,
                    agent_id,
                    session_id,
                    memory_type.value,
                    key,
                ),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return MemoryEntry(
                id=row[0],
                workflow_id=row[1],
                execution_id=row[2],
                agent_id=row[3],
                session_id=row[4],
                memory_type=MemoryType(row[5]),
                key=row[6],
                value=row[7],
                created_time=row[8],
                updated_time=row[9],
                expire_time=row[10],
            )
        finally:
            conn.close()

    async def delete_entry(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        memory_type: MemoryType,
        key: str,
    ) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM agent_memory_entries
                WHERE workflow_id = ? AND execution_id = ? AND agent_id = ? AND session_id = ? AND memory_type = ? AND key = ?
            """,
                (
                    workflow_id,
                    execution_id,
                    agent_id,
                    session_id,
                    memory_type.value,
                    key,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    async def query_entries(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        session_id: str,
        query: MemoryQuery,
    ) -> list[MemoryEntry]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT id, workflow_id, execution_id, agent_id, session_id, memory_type, key, value, created_time, updated_time, expire_time
                FROM agent_memory_entries
                WHERE workflow_id = ? AND execution_id = ? AND agent_id = ? AND session_id = ?
            """
            params: list[Any] = [workflow_id, execution_id, agent_id, session_id]

            if query.memory_type:
                sql += " AND memory_type = ?"
                params.append(query.memory_type.value)

            if query.key_prefix:
                sql += " AND key LIKE ?"
                params.append(f"{query.key_prefix}%")

            if query.search_query:
                sql += " AND value LIKE ?"
                params.append(f"%{query.search_query}%")

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            entries = []
            for r in rows:
                entry = MemoryEntry(
                    id=r[0],
                    workflow_id=r[1],
                    execution_id=r[2],
                    agent_id=r[3],
                    session_id=r[4],
                    memory_type=MemoryType(r[5]),
                    key=r[6],
                    value=r[7],
                    created_time=r[8],
                    updated_time=r[9],
                    expire_time=r[10],
                )
                entries.append(entry)
            return entries
        finally:
            conn.close()

    async def clear_expired(self, current_time: float) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM agent_memory_entries WHERE expire_time IS NOT NULL AND expire_time < ?",
                (current_time,),
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            conn.close()
