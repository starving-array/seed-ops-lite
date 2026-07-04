"""AgentManager orchestrating resolving, validation, execution, and metrics logging."""

import time
import uuid
from typing import Any

from app.agents.framework.models import (
    AgentExecutionContext,
    AgentExecutionRequest,
    AgentExecutionResult,
    AgentLifecycle,
)
from app.agents.framework.registry import AgentRegistry
from app.core.logging.logging import logger
from app.telemetry.events import EventID


class AgentManagerError(Exception):
    """Base exception for Manager errors."""

    pass


class AgentManager:
    """Orchestrates concrete agent lifecycle validation, run dispatching, and telemetry metrics tracking."""

    def __init__(self, registry: AgentRegistry) -> None:
        """Initialize the AgentManager.

        Args:
            registry: AgentRegistry containing discoverable agents.
        """
        self.registry = registry
        # Metrics map: agent_id -> metrics dict
        self._metrics: dict[str, dict[str, Any]] = {}

    def _get_or_init_metrics(self, agent_id: str) -> dict[str, Any]:
        if agent_id not in self._metrics:
            self._metrics[agent_id] = {
                "execution_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "average_duration": 0.0,
                "max_duration": 0.0,
                "agent_availability": True,
                "last_execution": None,
                "health_status": "Healthy",
            }
        return self._metrics[agent_id]

    def get_metrics(self, agent_id: str) -> dict[str, Any]:
        """Retrieve telemetry metrics for a specific agent.

        Args:
            agent_id: Identification string of the target agent.

        Returns:
            Dict[str, Any]: Compiled telemetry metrics dictionary copy.
        """
        metrics = self._get_or_init_metrics(agent_id)
        return dict(metrics)

    async def execute_agent(
        self,
        agent_id: str,
        inputs: dict[str, Any],
        variables: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        workflow_version: str = "1.0.0",
    ) -> AgentExecutionResult:
        """Resolve, validate, execute, and record metrics for a target agent.

        Args:
            agent_id: Target agent to trigger.
            inputs: User-supplied parameters map.
            variables: Scoped context variables.
            workflow_id: Target execution workflow context.
            workflow_version: Execution semantic version mapping.

        Returns:
            AgentExecutionResult: Execution summary report payload.

        Raises:
            AgentManagerError: On validation failure or initialization error.
        """
        # Resolve target agent
        try:
            agent = self.registry.lookup(agent_id)
        except Exception as exc:
            raise AgentManagerError(
                f"Failed to resolve agent '{agent_id}': {exc}"
            ) from exc

        meta = agent.metadata()
        metrics = self._get_or_init_metrics(meta.id)
        metrics["execution_count"] += 1
        metrics["last_execution"] = time.time()

        # Validate configuration / availability
        if hasattr(agent, "configuration"):
            config = agent.configuration
            if not config.enabled:
                metrics["failure_count"] += 1
                logger.warning(
                    EventID.LOG_WARNING,
                    f"Agent execution blocked: Agent '{meta.id}' is disabled.",
                    component="AgentManager",
                    agent_id=meta.id,
                )
                return AgentExecutionResult(
                    execution_id=str(uuid.uuid4()),
                    status=AgentLifecycle.DISABLED,
                    outputs={},
                    errors=[f"Agent '{meta.id}' is disabled."],
                    duration=0.0,
                )

        # 1. Initialize
        logger.info(
            EventID.LOG_INFO,
            f"Agent execution initiated: {meta.name}",
            component="AgentManager",
            agent_id=meta.id,
        )
        await agent.initialize()

        # 2. Validate readiness
        is_ready = await agent.validate()
        if not is_ready:
            metrics["failure_count"] += 1
            await agent.cleanup()
            raise AgentManagerError(f"Agent validation check failed for '{meta.id}'.")

        # 3. Create context & request
        exec_id = str(uuid.uuid4())
        wf_id = workflow_id or f"wf-{exec_id}"
        vars_map = variables or {}

        req = AgentExecutionRequest(
            execution_id=exec_id,
            workflow_id=wf_id,
            inputs=inputs,
            variables=vars_map,
        )

        ctx = AgentExecutionContext(
            execution_id=exec_id,
            workflow_id=wf_id,
            workflow_version=workflow_version,
            variables=vars_map,
            inputs=inputs,
            outputs={},
        )

        # 4. Execute
        start_time = time.perf_counter()
        try:
            response = await agent.execute(req, ctx)
            duration = time.perf_counter() - start_time

            # Update metrics
            if response.status == AgentLifecycle.COMPLETED:
                metrics["success_count"] += 1
            else:
                metrics["failure_count"] += 1

            metrics["max_duration"] = max(metrics["max_duration"], duration)
            total_runs = metrics["success_count"] + metrics["failure_count"]
            # Accumulate average duration
            metrics["average_duration"] = (
                metrics["average_duration"] * (total_runs - 1) + duration
            ) / total_runs

            logger.info(
                EventID.LOG_INFO,
                f"Agent execution completed: {meta.name} ({response.status.value})",
                component="AgentManager",
                agent_id=meta.id,
                duration=round(duration, 3),
            )

            return AgentExecutionResult(
                execution_id=exec_id,
                status=response.status,
                outputs=response.outputs,
                errors=response.errors,
                duration=duration,
                metrics=response.metrics,
            )

        except Exception as exc:
            duration = time.perf_counter() - start_time
            metrics["failure_count"] += 1
            logger.error(
                EventID.LOG_ERROR,
                f"Agent execution failed: {meta.name}. Error: {exc}",
                component="AgentManager",
                agent_id=meta.id,
                error=str(exc),
            )
            return AgentExecutionResult(
                execution_id=exec_id,
                status=AgentLifecycle.FAILED,
                outputs={},
                errors=[str(exc)],
                duration=duration,
            )
        finally:
            await agent.cleanup()
