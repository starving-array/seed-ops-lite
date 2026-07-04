"""Thread-safe ToolRegistry managing concrete tool registration and discovery."""

import threading

from app.agents.tools.interface import Tool
from app.agents.tools.models import ToolCapability, ToolCategory


class ToolRegistryError(Exception):
    """Base exception for Registry errors."""

    pass


class ToolRegistry:
    """Discovery and registration directory matching agents to execution tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._lock = threading.RLock()

    def register(self, tool: Tool) -> None:
        """Register a concrete tool. Prevents duplicates.

        Args:
            tool: Pluggable concrete tool.

        Raises:
            ToolRegistryError: If tool identifier is already registered.
        """
        meta = tool.metadata()
        with self._lock:
            if meta.id in self._tools:
                raise ToolRegistryError(
                    f"Tool with ID '{meta.id}' is already registered."
                )
            self._tools[meta.id] = tool

            from app.core.logging.logging import logger
            from app.telemetry.events import EventID

            logger.info(
                EventID.LOG_INFO,
                f"Tool registered: {meta.name} (ID: {meta.id}, Version: {meta.version})",
                component="ToolRegistry",
                tool_id=meta.id,
                tool_version=meta.version,
            )

    def unregister(self, tool_id: str) -> None:
        """Remove a tool from registration.

        Args:
            tool_id: Key mapping string.
        """
        with self._lock:
            self._tools.pop(tool_id, None)

    def lookup(self, tool_id: str) -> Tool:
        """Retrieve a registered tool by ID.

        Args:
            tool_id: Target tool key identifier.

        Returns:
            Tool: The matching Concrete Tool.

        Raises:
            ToolRegistryError: If no tool matches.
        """
        with self._lock:
            tool = self._tools.get(tool_id)
            if tool is None:
                raise ToolRegistryError(
                    f"No tool found matching identifier '{tool_id}'"
                )
            return tool

    def lookup_by_capability(self, capability: ToolCapability) -> list[Tool]:
        """Lookup tools matching a specific capability.

        Args:
            capability: Capability filter tag.

        Returns:
            List[Tool]: Matching tools list.
        """
        with self._lock:
            matching = []
            for tool in self._tools.values():
                meta = tool.metadata()
                if capability in meta.capabilities:
                    matching.append(tool)
            return matching

    def lookup_by_category(self, category: ToolCategory) -> list[Tool]:
        """Lookup tools matching a specific category.

        Args:
            category: Classification category.

        Returns:
            List[Tool]: Matching tools list.
        """
        with self._lock:
            matching = []
            for tool in self._tools.values():
                meta = tool.metadata()
                if meta.category == category:
                    matching.append(tool)
            return matching

    def list_tools(self) -> list[Tool]:
        """Return list of all registered tools.

        Returns:
            List[Tool]: Active listings.
        """
        with self._lock:
            return list(self._tools.values())

    async def get_health_summary(self) -> dict[str, bool]:
        """Run health audits across all registered concrete tools.

        Returns:
            Dict[str, bool]: Registry health status mappings.
        """
        with self._lock:
            tools_copy = list(self._tools.items())

        results = {}
        for tid, tool in tools_copy:
            try:
                results[tid] = await tool.health()
            except Exception:
                results[tid] = False
        return results
