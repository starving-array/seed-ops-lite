"""Agent Execution Integration Layer uniting Workflow, Memory, Tools, and Runtime."""

import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agents.execution.models import ExecutionContext
from app.agents.memory.manager import AgentMemoryManager
from app.agents.tools.manager import ToolManager
from app.agents.tools.models import ToolPermission, ToolResponse
from app.core.logging.logging import logger
from app.platform.container import get_persistence_provider
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.telemetry.events import EventID


class ExecutionIntegrationResult(BaseModel):
    """Result summary detailing synchronization changes, execution metrics, and latency."""

    model_config = ConfigDict(frozen=True)

    success: bool
    synchronized_keys: list[str] = Field(default_factory=list)
    latency: float = 0.0
    errors: list[str] = Field(default_factory=list)


class WorkflowExecutionAdapter:
    """Bridges Execution Orchestrator to Workflow persistence providers."""

    def __init__(self) -> None:
        self.persistence = get_persistence_provider()

    async def load_context(self, workflow_id: str, execution_id: str) -> dict[str, Any]:
        """Verify workflow exists and fetch execution metrics state."""
        # Validate workflow existence
        try:
            job = await self.persistence.get_job(execution_id)
            if not job:
                raise ValueError(
                    f"Job/execution with ID '{execution_id}' does not exist."
                )
            logger.info(
                EventID.LOG_INFO,
                f"Workflow loaded successfully for workflow: {workflow_id}",
                component="WorkflowExecutionAdapter",
            )
            return job
        except Exception as exc:
            logger.error(
                EventID.LOG_ERROR,
                f"Failed to load workflow context: {exc}",
                component="WorkflowExecutionAdapter",
            )
            raise

    async def update_status(self, execution_id: str, status: str) -> None:
        """Propagate execution state changes back to workflow persistence models."""
        try:
            await self.persistence.update_job_status(execution_id, status, progress=0.0)
        except Exception as exc:
            logger.error(
                EventID.LOG_ERROR,
                f"Failed to update workflow status: {exc}",
                component="WorkflowExecutionAdapter",
            )
            raise


class MemoryExecutionAdapter:
    """Integrates Orchestrator runs with versioned, isolated AgentMemoryManager sessions."""

    def __init__(self, memory_manager: AgentMemoryManager) -> None:
        self.memory_manager = memory_manager

    async def load_memory(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        keys: list[str],
    ) -> dict[str, Any]:
        """Fetch memory variables for an isolated session."""
        try:
            from app.agents.memory.models import MemoryType

            res = {}
            for key in keys:
                val = await self.memory_manager.read(
                    workflow_id,
                    execution_id,
                    agent_id,
                    "session",
                    MemoryType.SHORT_TERM,
                    key,
                )
                if val is not None:
                    res[key] = val
            logger.info(
                EventID.LOG_INFO,
                "Memory restored successfully for isolated session.",
                component="MemoryExecutionAdapter",
            )
            return res
        except Exception as exc:
            logger.error(
                EventID.LOG_ERROR,
                f"Failed to load memory context: {exc}",
                component="MemoryExecutionAdapter",
            )
            raise

    async def save_variable(
        self,
        workflow_id: str,
        execution_id: str,
        agent_id: str,
        key: str,
        value: Any,
    ) -> None:
        """Write execution variable safely into the persistence engine."""
        try:
            from app.agents.memory.models import MemoryType

            await self.memory_manager.write(
                workflow_id,
                execution_id,
                agent_id,
                "session",
                MemoryType.SHORT_TERM,
                key,
                value,
            )
        except Exception as exc:
            logger.error(
                EventID.LOG_ERROR,
                f"Failed to save variable: {exc}",
                component="MemoryExecutionAdapter",
            )
            raise


class ToolExecutionAdapter:
    """Safely routes tool calls through ToolManager, enforcing scope boundaries."""

    def __init__(self, tool_manager: ToolManager) -> None:
        self.tool_manager = tool_manager

    async def invoke_tool(
        self,
        tool_id: str,
        inputs: dict[str, Any],
        context: Any,
        granted_permissions: list[ToolPermission],
    ) -> ToolResponse:
        """Route tool calls securely checking authorization registry permissions."""
        logger.info(
            EventID.LOG_INFO,
            f"Tool invoked: {tool_id}",
            component="ToolExecutionAdapter",
        )
        # Execute tool via ToolManager
        return await self.tool_manager.execute_tool(
            tool_id=tool_id,
            inputs=inputs,
            context=context,
            granted_permissions=granted_permissions,
        )


class RuntimeExecutionAdapter:
    """Manages secure runtime diagnostics queries and pool health lookups."""

    @staticmethod
    def check_health() -> bool:
        """Determine runtime database readiness without direct Redis access."""
        try:
            sqlite_db_manager.verify_health()
            logger.info(
                EventID.LOG_INFO,
                "Runtime resolved successfully.",
                component="RuntimeExecutionAdapter",
            )
            return True
        except Exception as exc:
            logger.error(
                EventID.LOG_ERROR,
                f"Runtime health check failed: {exc}",
                component="RuntimeExecutionAdapter",
            )
            return False


class ExecutionIntegrationManager:
    """Orchestrates integrations, variable syncs, and telemetry diagnostics telemetry logging."""

    def __init__(
        self,
        memory_manager: AgentMemoryManager,
        tool_manager: ToolManager,
    ) -> None:
        self.workflow_adapter = WorkflowExecutionAdapter()
        self.memory_adapter = MemoryExecutionAdapter(memory_manager)
        self.tool_adapter = ToolExecutionAdapter(tool_manager)
        self.runtime_adapter = RuntimeExecutionAdapter()
        self._metrics = {
            "workflow_integrations": 0,
            "memory_lookups": 0,
            "memory_updates": 0,
            "tool_invocations": 0,
            "runtime_lookups": 0,
            "integration_failures": 0,
        }

    def get_metrics(self) -> dict[str, Any]:
        """Fetch telemetry statistics tracking integration adapters."""
        return dict(self._metrics)

    async def synchronize_context(
        self,
        context: ExecutionContext,
        variables: dict[str, Any],
    ) -> ExecutionIntegrationResult:
        """Sync workflow variables, memory state, and runtime environment attributes.

        Args:
            context: Scoped execution context variables.
            variables: Target variables to synchronize.

        Returns:
            ExecutionIntegrationResult: Sync diagnostics metrics summary.
        """
        start_time = time.perf_counter()
        sync_keys: list[str] = []
        errors: list[str] = []

        try:
            # 1. Runtime database health lookup
            self._metrics["runtime_lookups"] += 1
            if not self.runtime_adapter.check_health():
                errors.append("Runtime database connection pool is unhealthy.")

            # 2. Workflow Context Verification
            self._metrics["workflow_integrations"] += 1
            await self.workflow_adapter.load_context(
                context.workflow_id, context.execution_id
            )

            # 3. Synchronize Memory variables
            self._metrics["memory_lookups"] += 1
            current_mem = await self.memory_adapter.load_memory(
                context.workflow_id,
                context.execution_id,
                context.agent_id,
                list(variables.keys()),
            )

            for key, val in variables.items():
                if current_mem.get(key) != val:
                    self._metrics["memory_updates"] += 1
                    await self.memory_adapter.save_variable(
                        context.workflow_id,
                        context.execution_id,
                        context.agent_id,
                        key,
                        val,
                    )
                    sync_keys.append(key)

            latency = time.perf_counter() - start_time
            success = len(errors) == 0

            if not success:
                self._metrics["integration_failures"] += 1
                logger.warning(
                    EventID.LOG_WARNING,
                    f"Integration failed: {errors}",
                    component="ExecutionIntegrationManager",
                )
            else:
                logger.info(
                    EventID.LOG_INFO,
                    "Integration completed successfully.",
                    component="ExecutionIntegrationManager",
                )

            return ExecutionIntegrationResult(
                success=success,
                synchronized_keys=sync_keys,
                latency=latency,
                errors=errors,
            )

        except Exception as exc:
            self._metrics["integration_failures"] += 1
            latency = time.perf_counter() - start_time
            logger.error(
                EventID.LOG_ERROR,
                f"Integration synchronization exception: {exc}",
                component="ExecutionIntegrationManager",
            )
            return ExecutionIntegrationResult(
                success=False,
                synchronized_keys=sync_keys,
                latency=latency,
                errors=[str(exc)],
            )
