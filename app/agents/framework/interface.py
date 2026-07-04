"""Abstract Base Class interface defining execution contract for all Concrete Agents."""

from abc import ABC, abstractmethod

from app.agents.framework.models import (
    AgentExecutionContext,
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentMetadata,
)


class Agent(ABC):
    """Abstract interface contract for pluggable Concrete Agents."""

    @abstractmethod
    async def initialize(self) -> None:
        """Perform startup allocation, resource initialization, and registry setups."""
        pass

    @abstractmethod
    async def validate(self) -> bool:
        """Validate agent readiness, capability constraints, and active settings."""
        pass

    @abstractmethod
    async def execute(
        self, request: AgentExecutionRequest, context: AgentExecutionContext
    ) -> AgentExecutionResponse:
        """Execute the agent process block synchronously or asynchronously.

        Args:
            request: Inbound execution variables.
            context: Scoped workflow run parameters.

        Returns:
            AgentExecutionResponse: The outcome response mapping status and outputs.
        """
        pass

    @abstractmethod
    async def cancel(self, execution_id: str) -> None:
        """Cancel an ongoing step execution, triggering downstream cleanups.

        Args:
            execution_id: Tracking ID of the task to abort.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Deallocate resources, shut down provider connections, and clean local context."""
        pass

    @abstractmethod
    async def health(self) -> bool:
        """Verify the health status of external providers, APIs, or internal engines.

        Returns:
            bool: True if agent state is fully functional and healthy.
        """
        pass

    @abstractmethod
    def metadata(self) -> AgentMetadata:
        """Retrieve semantic description, versioning, and identify keys.

        Returns:
            AgentMetadata: Static author and naming identification specifications.
        """
        pass
