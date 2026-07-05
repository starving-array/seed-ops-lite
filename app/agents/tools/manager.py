"""ToolManager coordinating validation, concurrency, permissions, retries, and metrics collection."""

import asyncio
import time
from typing import Any

from app.agents.tools.models import (
    ToolContext,
    ToolPermission,
    ToolRequest,
    ToolResponse,
    ToolStatistics,
)
from app.agents.tools.registry import ToolRegistry
from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.telemetry.events import EventID


class ToolManagerError(Exception):
    """Base exception for ToolManager errors."""

    pass


class ToolPermissionDeniedError(ToolManagerError):
    """Exception raised when permission checks fail."""

    pass


class ToolExecutionTimeoutError(ToolManagerError):
    """Exception raised when a tool execution times out."""

    pass


class ToolManager:
    """Orchestrates security validation, concurrency, retry logic, and performance metrics."""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry
        self._concurrency_semaphore = asyncio.Semaphore(
            platform_settings.TOOLS_MAX_CONCURRENT_EXECUTIONS
        )
        self._metrics: dict[str, ToolStatistics] = {}

    def _get_or_init_metrics(self, tool_id: str) -> ToolStatistics:
        if tool_id not in self._metrics:
            # Stats are immutable models, so we track a mutable dict internally and convert on query
            self._metrics[tool_id] = ToolStatistics()
        return self._metrics[tool_id]

    def _update_stats(self, tool_id: str, **kwargs: Any) -> None:
        stats = self._get_or_init_metrics(tool_id)
        # Create a new statistics model with updated values
        current_data = stats.model_dump()
        current_data.update(kwargs)
        self._metrics[tool_id] = ToolStatistics(**current_data)

    def get_metrics(self, tool_id: str) -> ToolStatistics:
        """Fetch compiled execution telemetry statistics for a tool.

        Args:
            tool_id: Target tool identifier.

        Returns:
            ToolStatistics: Immutable telemetry stats.
        """
        return self._get_or_init_metrics(tool_id)

    async def execute_tool(
        self,
        tool_id: str,
        inputs: dict[str, Any],
        context: ToolContext,
        granted_permissions: list[ToolPermission],
    ) -> ToolResponse:
        """Resolve, authenticate, validate, and execute a tool under timeout and concurrency locks.

        Args:
            tool_id: Identification of target tool to run.
            inputs: Parameters map inputs.
            context: Scoped execution context details.
            granted_permissions: Access rights granted to the execution context.

        Returns:
            ToolResponse: Standardized outcome response.

        Raises:
            ToolManagerError: On registry resolution errors.
        """
        try:
            tool = self.registry.lookup(tool_id)
        except Exception as exc:
            raise ToolManagerError(
                f"Failed to resolve tool '{tool_id}': {exc}"
            ) from exc

        meta = tool.metadata()
        stats = self._get_or_init_metrics(meta.id)
        self._update_stats(meta.id, execution_count=stats.execution_count + 1)

        # 1. Validate Permissions
        for required in meta.permissions_required:
            if required not in granted_permissions:
                self._update_stats(
                    meta.id, permission_denials=stats.permission_denials + 1
                )
                logger.warning(
                    EventID.LOG_WARNING,
                    f"Permission Denied: Tool '{meta.id}' requires '{required.value}' permission.",
                    component="ToolManager",
                    tool_id=meta.id,
                )
                return ToolResponse(
                    success=False,
                    outputs={},
                    errors=[
                        f"Permission Denied: Missing required permission '{required.value}'"
                    ],
                    duration=0.0,
                )

        # Build Request
        request = ToolRequest(
            tool_id=meta.id,
            inputs=inputs,
            context=context,
        )

        # 2. Concurrency check & Initialize
        async with self._concurrency_semaphore:
            logger.info(
                EventID.LOG_INFO,
                f"Tool executed: {meta.name}",
                component="ToolManager",
                tool_id=meta.id,
            )
            await tool.initialize()

            # 3. Validate Inputs
            is_valid = await tool.validate(request)
            if not is_valid:
                await tool.cleanup()
                self._update_stats(meta.id, failure_count=stats.failure_count + 1)
                return ToolResponse(
                    success=False,
                    outputs={},
                    errors=["Input validation checks failed."],
                    duration=0.0,
                )

            # 4. Execute with Timeout & Retries
            max_retries = platform_settings.TOOLS_MAX_RETRIES
            timeout_limit = platform_settings.TOOLS_MAX_EXECUTION_TIMEOUT_SECONDS
            attempt = 0
            start_time = time.perf_counter()

            while attempt <= max_retries:
                try:
                    # Run execution wrapped inside a timeout
                    response = await asyncio.wait_for(
                        tool.execute(request, context),
                        timeout=timeout_limit,
                    )
                    duration = time.perf_counter() - start_time

                    # Update statistics
                    if response.success:
                        self._update_stats(
                            meta.id, success_count=stats.success_count + 1
                        )
                        logger.info(
                            EventID.LOG_INFO,
                            f"Tool completed: {meta.name} successfully.",
                            component="ToolManager",
                            tool_id=meta.id,
                            duration=round(duration, 3),
                        )
                    else:
                        self._update_stats(
                            meta.id, failure_count=stats.failure_count + 1
                        )
                        logger.info(
                            EventID.LOG_INFO,
                            f"Tool failed: {meta.name} execution failed.",
                            component="ToolManager",
                            tool_id=meta.id,
                            duration=round(duration, 3),
                        )

                    # Update average execution time
                    total_runs = stats.success_count + stats.failure_count + 1
                    avg_time = (
                        stats.average_execution_time * (total_runs - 1) + duration
                    ) / total_runs
                    self._update_stats(meta.id, average_execution_time=avg_time)

                    await tool.cleanup()
                    return response

                except TimeoutError:
                    self._update_stats(meta.id, timeouts=stats.timeouts + 1)
                    logger.warning(
                        EventID.LOG_WARNING,
                        f"Timeout: Tool '{meta.id}' timed out after {timeout_limit} seconds.",
                        component="ToolManager",
                        tool_id=meta.id,
                    )
                    await tool.cleanup()
                    return ToolResponse(
                        success=False,
                        outputs={},
                        errors=[f"Execution timed out after {timeout_limit} seconds."],
                        duration=time.perf_counter() - start_time,
                    )

                except Exception as exc:
                    attempt += 1
                    self._update_stats(meta.id, retries=stats.retries + 1)
                    if attempt > max_retries:
                        duration = time.perf_counter() - start_time
                        self._update_stats(
                            meta.id, failure_count=stats.failure_count + 1
                        )
                        logger.error(
                            EventID.LOG_ERROR,
                            f"Tool failed: {meta.name} failed after {max_retries} retries.",
                            component="ToolManager",
                            tool_id=meta.id,
                            error=str(exc),
                        )
                        await tool.cleanup()
                        return ToolResponse(
                            success=False,
                            outputs={},
                            errors=[f"Execution failed after retries: {exc}"],
                            duration=duration,
                        )
                    # Small backoff before retry attempt
                    await asyncio.sleep(0.05)

            return ToolResponse(
                success=False,
                outputs={},
                errors=["Execution failed: unexpected end of retry loop."],
                duration=time.perf_counter() - start_time,
            )
