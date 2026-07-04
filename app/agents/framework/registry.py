"""Thread-safe AgentRegistry managing concrete agent lifecycle, registration, and discovery."""

import threading

from app.agents.framework.interface import Agent
from app.agents.framework.models import AgentCapability


class AgentRegistryError(Exception):
    """Base exception for Registry errors."""

    pass


class AgentRegistry:
    """Discovery and registration directory matching agents to execution requests."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._lock = threading.RLock()

    def register(self, agent: Agent) -> None:
        """Register a new agent instance. Prevents duplicate ID registrations.

        Args:
            agent: Instantiated Concrete Agent.

        Raises:
            AgentRegistryError: If an agent with the same ID is already registered.
        """
        meta = agent.metadata()
        with self._lock:
            if meta.id in self._agents:
                raise AgentRegistryError(
                    f"Agent with ID '{meta.id}' is already registered in the registry."
                )
            self._agents[meta.id] = agent

            # Avoid circular import, import logger locally
            from app.core.logging.logging import logger
            from app.telemetry.events import EventID

            logger.info(
                EventID.LOG_INFO,
                f"Agent registered: {meta.name} (ID: {meta.id}, Version: {meta.version})",
                component="AgentRegistry",
                agent_id=meta.id,
                agent_version=meta.version,
            )

    def unregister(self, agent_id: str) -> None:
        """Unregister an agent by ID.

        Args:
            agent_id: Identification string of the target agent to remove.
        """
        with self._lock:
            if agent_id in self._agents:
                self._agents.pop(agent_id)

    def lookup(self, agent_id: str) -> Agent:
        """Find a registered agent by ID.

        Args:
            agent_id: Target agent identifier.

        Returns:
            Agent: The matching Concrete Agent.

        Raises:
            AgentRegistryError: If the agent is not found.
        """
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                raise AgentRegistryError(
                    f"No agent found matching identifier '{agent_id}'"
                )
            return agent

    def lookup_by_capability(self, capability: AgentCapability) -> list[Agent]:
        """Find all registered agents supporting a specific capability.

        Args:
            capability: Requested skill enum.

        Returns:
            List[Agent]: Matching concrete agents list.
        """
        with self._lock:
            matching = []
            for agent in self._agents.values():
                # Concrete agents can declare capability arrays or return them via definitions
                # We assume a capabilities property or capability checking helper
                # Let's inspect capabilities if available
                meta = agent.metadata()
                # To support dynamic capabilities check, check if agent has target attribute or method
                if hasattr(agent, "capabilities"):
                    caps = agent.capabilities
                elif hasattr(agent, "get_capabilities"):
                    caps = agent.get_capabilities()
                else:
                    caps = getattr(meta, "capabilities", [])

                if capability in caps:
                    matching.append(agent)
            return matching

    def list_agents(self) -> list[Agent]:
        """List all currently registered concrete agents.

        Returns:
            List[Agent]: All active registry listings.
        """
        with self._lock:
            return list(self._agents.values())

    async def check_health(self) -> dict[str, bool]:
        """Run health audits across all registered concrete agents.

        Returns:
            Dict[str, bool]: Dictionary mapping Agent IDs to health statuses.
        """
        results = {}
        # Fetch copy under lock to prevent holding lock during async network calls
        with self._lock:
            agents_copy = list(self._agents.items())

        for aid, agent in agents_copy:
            try:
                results[aid] = await agent.health()
            except Exception:
                results[aid] = False
        return results
