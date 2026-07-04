"""Multi-Agent Task Delegation Engine."""

# ruff: noqa: S110, S112, B904, RUF005, RET505

import time
from enum import Enum

from pydantic import BaseModel

from app.agents.collaboration.models import (
    AgentTask,
    DelegationRequest,
    DelegationResult,
)
from app.agents.framework.manager import AgentManager
from app.agents.framework.models import AgentLifecycle
from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.telemetry.events import EventID


class DelegationPolicy(str, Enum):
    """Supported task delegation assignment policies."""

    DIRECT_ASSIGNMENT = "DIRECT_ASSIGNMENT"
    BEST_CAPABILITY = "BEST_CAPABILITY"
    ROUND_ROBIN = "ROUND_ROBIN"
    LEAST_BUSY = "LEAST_BUSY"
    FIRST_AVAILABLE = "FIRST_AVAILABLE"


class DelegationStatistics(BaseModel):
    """Accumulates delegation events execution telemetry."""

    requests: int = 0
    successes: int = 0
    failures: int = 0
    rejections: int = 0
    delegation_depth_max: int = 0
    delegated_task_count: int = 0
    total_assignment_time: float = 0.0


class DelegationValidator:
    """Validates delegation requests constraints."""

    @staticmethod
    def validate_request(
        request: DelegationRequest,
        agent_manager: AgentManager,
        delegation_chain: list[str],
    ) -> None:
        """Validate agent status, depth limits, and check circular delegation.

        Raises:
            ValueError: On validation checks failures.
        """
        # 1. Depth check
        max_depth = platform_settings.MULTI_AGENT_MAX_DELEGATION_DEPTH
        current_depth = len(delegation_chain)
        if current_depth >= max_depth:
            raise ValueError(
                f"Delegation depth limit '{max_depth}' exceeded. Current depth: {current_depth}"
            )

        # 2. Circular delegation check
        child_id = request.child_agent_id
        if child_id in delegation_chain:
            raise ValueError(
                f"Circular delegation detected. Agent '{child_id}' is already in delegation chain: {delegation_chain}"
            )

        # 3. Agent existence check
        try:
            agent_instance = agent_manager.registry.lookup(child_id)
        except Exception:
            raise ValueError(f"Target child agent '{child_id}' does not exist.")

        # 4. Availability/Enabled check
        metrics = agent_manager.get_metrics(child_id)
        if not metrics.get("agent_availability", True):
            raise ValueError(f"Target child agent '{child_id}' is currently disabled.")

        # 5. Healthy check
        if metrics.get("health_status", "Healthy") != "Healthy":
            raise ValueError(f"Target child agent '{child_id}' is unhealthy.")

        # 6. Capabilities check
        required = request.delegated_task.capabilities_required
        if required:
            supported = getattr(agent_instance, "capabilities", [])
            missing = [cap for cap in required if cap not in supported]
            if missing:
                raise ValueError(
                    f"Agent '{child_id}' lacks required capabilities: {missing}"
                )


class AssignmentManager:
    """Selects eligible agents based on role, capability, and policy conditions."""

    def __init__(self, agent_manager: AgentManager) -> None:
        self.agent_manager = agent_manager
        self._round_robin_index = 0

    def select_agent(
        self,
        task: AgentTask,
        policy: DelegationPolicy,
        candidates: list[str],
    ) -> str:
        """Select target agent ID from candidates based on policy rules."""
        if not candidates:
            raise ValueError("No candidate agents provided for selection.")

        # Filter candidates to exist in registry
        valid_candidates = []
        for cid in candidates:
            try:
                self.agent_manager.registry.lookup(cid)
                valid_candidates.append(cid)
            except Exception:
                pass
        if not valid_candidates:
            raise ValueError("No valid agents found in the candidates list.")

        if policy == DelegationPolicy.DIRECT_ASSIGNMENT:
            # Enforce task's explicit assigned agent ID
            target = task.assigned_agent_id
            if target not in valid_candidates:
                raise ValueError(
                    f"Direct assignment target '{target}' is not in candidate list."
                )
            return target

        if policy == DelegationPolicy.BEST_CAPABILITY:
            # Select agent with the highest count of matched capabilities
            best_agent = valid_candidates[0]
            best_count = -1
            for cid in valid_candidates:
                try:
                    agent = self.agent_manager.registry.lookup(cid)
                except Exception:
                    continue
                supported = getattr(agent, "capabilities", [])
                match_count = len(
                    set(task.capabilities_required).intersection(supported)
                )
                if match_count > best_count:
                    best_count = match_count
                    best_agent = cid
            return best_agent

        if policy == DelegationPolicy.ROUND_ROBIN:
            target = valid_candidates[self._round_robin_index % len(valid_candidates)]
            self._round_robin_index += 1
            return target

        if policy == DelegationPolicy.LEAST_BUSY:
            # Select agent with least execution count from metrics
            least_busy = valid_candidates[0]
            min_execs = float("inf")
            for cid in valid_candidates:
                m = self.agent_manager.get_metrics(cid)
                exec_count = m.get("execution_count", 0)
                if exec_count < min_execs:
                    min_execs = exec_count
                    least_busy = cid
            return least_busy

        # DEFAULT: First available
        return valid_candidates[0]


class DelegationEngine:
    """Core delegation execution coordinator orchestrating requests lifecycle."""

    def __init__(self, agent_manager: AgentManager) -> None:
        self.agent_manager = agent_manager
        self.assignment_manager = AssignmentManager(agent_manager)
        self.statistics = DelegationStatistics()
        self._delegation_chains: dict[str, list[str]] = {}

    async def delegate_task(
        self,
        request: DelegationRequest,
        policy: DelegationPolicy = DelegationPolicy.DIRECT_ASSIGNMENT,
        candidates: list[str] | None = None,
    ) -> DelegationResult:
        """Process delegation task routing, validation, and invoke task execution runner."""
        start_time = time.perf_counter()
        self.statistics.requests += 1

        logger.info(
            EventID.LOG_INFO,
            f"Delegation requested from '{request.parent_agent_id}' to '{request.child_agent_id}'",
            component="DelegationEngine",
        )

        # Build / retrieve parent chain
        parent_chain = self._delegation_chains.get(request.parent_agent_id, [])
        chain = parent_chain + [request.parent_agent_id]

        try:
            # 1. Selection adjustment if policy dictates
            target_agent = request.child_agent_id
            if policy != DelegationPolicy.DIRECT_ASSIGNMENT and candidates:
                target_agent = self.assignment_manager.select_agent(
                    request.delegated_task, policy, candidates
                )
                # Rebuild request with resolved child
                request = DelegationRequest(
                    request_id=request.request_id,
                    parent_agent_id=request.parent_agent_id,
                    child_agent_id=target_agent,
                    delegated_task=request.delegated_task,
                    assignment_metadata=request.assignment_metadata,
                    retry_policy_reference=request.retry_policy_reference,
                )

            # 2. Validation
            DelegationValidator.validate_request(request, self.agent_manager, chain)

            # Record chain mapping for current child
            self._delegation_chains[target_agent] = chain

            # 3. Track statistics
            self.statistics.delegated_task_count += 1
            self.statistics.delegation_depth_max = max(
                self.statistics.delegation_depth_max, len(chain)
            )

            # 4. Dispatch execution via AgentManager
            logger.info(
                EventID.LOG_INFO,
                f"Delegation accepted. Running task '{request.delegated_task.task_id}' on child '{target_agent}'",
                component="DelegationEngine",
            )
            res = await self.agent_manager.execute_agent(
                agent_id=target_agent,
                inputs=request.assignment_metadata,
                workflow_id="delegated-wf",
            )

            duration = time.perf_counter() - start_time
            self.statistics.total_assignment_time += duration

            if res.status == AgentLifecycle.COMPLETED:
                self.statistics.successes += 1
                logger.info(
                    EventID.LOG_INFO,
                    f"Delegation completed successfully for request '{request.request_id}'",
                    component="DelegationEngine",
                )
                return DelegationResult(
                    request_id=request.request_id,
                    success=True,
                    outputs=res.outputs,
                    errors=[],
                )
            else:
                self.statistics.failures += 1
                logger.error(
                    EventID.LOG_ERROR,
                    f"Delegation failed for request '{request.request_id}': {res.errors}",
                    component="DelegationEngine",
                )
                return DelegationResult(
                    request_id=request.request_id,
                    success=False,
                    outputs={},
                    errors=res.errors,
                )

        except Exception as err:
            self.statistics.rejections += 1
            duration = time.perf_counter() - start_time
            self.statistics.total_assignment_time += duration
            logger.error(
                EventID.LOG_ERROR,
                f"Delegation rejected: {err}",
                component="DelegationEngine",
            )
            return DelegationResult(
                request_id=request.request_id,
                success=False,
                outputs={},
                errors=[str(err)],
            )
        finally:
            # Clean chain registry mapping if exists
            self._delegation_chains.pop(request.child_agent_id, None)
