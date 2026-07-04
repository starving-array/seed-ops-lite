"""Abstract interface defining the execution contract for all Concrete Tools."""

from abc import ABC, abstractmethod

from app.agents.tools.models import ToolContext, ToolMetadata, ToolRequest, ToolResponse


class Tool(ABC):
    """Abstract interface contract governing pluggable Concrete Tools."""

    @abstractmethod
    async def initialize(self) -> None:
        """Perform tool startup, allocate system resource hooks, and set up sockets."""
        pass

    @abstractmethod
    async def validate(self, request: ToolRequest) -> bool:
        """Validate input parameters, argument types, and constraints before execute.

        Args:
            request: Inbound execution request parameters.

        Returns:
            bool: True if parameters match schema constraints and are valid.
        """
        pass

    @abstractmethod
    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResponse:
        """Execute the tool operation asynchronously.

        Args:
            request: Standardized request inputs payload.
            context: Scoped execution context variables.

        Returns:
            ToolResponse: Standardized outcome response.
        """
        pass

    @abstractmethod
    async def health(self) -> bool:
        """Verify the health status of external adapters, databases, or local runtimes.

        Returns:
            bool: True if tool is healthy and available.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Deallocate system handles, flush buffers, and disconnect pools."""
        pass

    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """Retrieve identifying specifications, version details, and required permissions.

        Returns:
            ToolMetadata: Static naming and permission authorization details.
        """
        pass
