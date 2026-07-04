"""Multi-Agent Inter-Agent Communication Bus."""

# ruff: noqa: RET508, RET505, S110, PLR0911

import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agents.framework.manager import AgentManager
from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.telemetry.events import EventID


class MessageType(str, Enum):
    """Supported inter-agent message types classification."""

    TASK_REQUEST = "TASK_REQUEST"
    TASK_RESPONSE = "TASK_RESPONSE"
    STATUS_UPDATE = "STATUS_UPDATE"
    EVENT = "EVENT"
    ERROR = "ERROR"
    HEARTBEAT = "HEARTBEAT"
    NOTIFICATION = "NOTIFICATION"
    SYSTEM = "SYSTEM"


class DeliveryPolicy(str, Enum):
    """Delivery behavior configurations."""

    FIRE_AND_FORGET = "FIRE_AND_FORGET"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    GUARANTEED_DELIVERY = "GUARANTEED_DELIVERY"
    RETRY_ON_FAILURE = "RETRY_ON_FAILURE"
    EXPIRE = "EXPIRE"


class MessageEnvelope(BaseModel):
    """Envelopes a message payload with routing and execution context metadata."""

    message_id: str = Field(..., description="Unique message identification UUID.")
    workflow_id: str = Field(..., description="Workflow execution scope context.")
    execution_id: str = Field(..., description="Active execution iteration context.")
    session_id: str = Field(
        ..., description="Collaboration session identification key."
    )
    sender_agent_id: str = Field(..., description="Identifier of the sender agent.")
    receiver_agent_id: str = Field(
        ..., description="Identifier of the destination receiver agent."
    )
    correlation_id: str = Field(
        ..., description="Correlation ID for task request/response tracking."
    )
    timestamp: float = Field(..., description="Epoch occurrence timestamp.")
    priority: int = Field(
        default=0, description="Message delivery priority order index."
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Variables map data."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata tags details."
    )
    message_type: MessageType = Field(..., description="Message classification type.")
    sequence_number: int = Field(
        default=0, description="Sequence counter for ordering guarantees."
    )
    ttl: float = Field(default=300.0, description="Time to live duration in seconds.")

    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Verify message payload serialization size against PlatformSettings limits."""
        limit = platform_settings.MULTI_AGENT_MAX_MESSAGE_SIZE
        # Rough estimation of payload content size by casting to string
        serialized_size = len(str(payload))
        if serialized_size > limit:
            raise ValueError(
                f"Message payload size '{serialized_size}' exceeds allowed limit '{limit}' bytes."
            )
        return payload


class MessageResult(BaseModel):
    """Outcome of a single message delivery attempt."""

    message_id: str = Field(..., description="Associated message envelope ID.")
    delivered: bool = Field(..., description="True if delivery completed.")
    acknowledged: bool = Field(
        default=False, description="True if receiver acknowledged receipt."
    )
    errors: list[str] = Field(
        default_factory=list, description="Logged delivery error messages."
    )
    retry_count: int = Field(
        default=0, description="Total delivery retry cycles completed."
    )


class CommunicationStatistics(BaseModel):
    """Aggregates metrics for the communication bus."""

    messages_sent: int = 0
    messages_received: int = 0
    messages_delivered: int = 0
    messages_failed: int = 0
    retries: int = 0
    expired_messages: int = 0
    average_delivery_time: float = 0.0
    queue_utilization: float = 0.0


class MessageDispatcher:
    """Delivers and retries messages strictly obeying DeliveryPolicy controls."""

    def __init__(self, agent_manager: AgentManager) -> None:
        self.agent_manager = agent_manager

    async def dispatch(
        self,
        envelope: MessageEnvelope,
        policy: DeliveryPolicy,
    ) -> MessageResult:
        """Deliver envelope payload to the destination agent."""
        logger.info(
            EventID.LOG_INFO,
            f"Dispatching message {envelope.message_id} to '{envelope.receiver_agent_id}' under policy '{policy}'",
            component="MessageDispatcher",
        )

        attempts = 0
        max_attempts = 1
        if policy in (
            DeliveryPolicy.RETRY_ON_FAILURE,
            DeliveryPolicy.GUARANTEED_DELIVERY,
        ):
            max_attempts = 1 + platform_settings.MULTI_AGENT_RETRY_ATTEMPTS

        errors = []
        acknowledged = False
        delivered = False

        while attempts < max_attempts:
            try:
                # 1. Expiration check
                age = time.time() - envelope.timestamp
                if age > envelope.ttl:
                    errors.append(f"Message expired. Age: {age}s, TTL: {envelope.ttl}s")
                    break

                # 2. Invoke dispatch via AgentManager using a TASK_REQUEST action if appropriate
                res = await self.agent_manager.execute_agent(
                    agent_id=envelope.receiver_agent_id,
                    inputs={
                        "message_payload": envelope.payload,
                        "message_type": envelope.message_type.value,
                        "sender_id": envelope.sender_agent_id,
                    },
                    workflow_id=envelope.workflow_id,
                )

                if (
                    res.status == "Completed"
                    or getattr(res.status, "value", None) == "Completed"
                ):
                    delivered = True
                    # Acknowledged policy requires confirmation
                    if policy != DeliveryPolicy.FIRE_AND_FORGET:
                        acknowledged = True
                    break
                else:
                    errors.append(f"Agent execution failure: {res.errors}")
            except Exception as err:
                errors.append(str(err))

            attempts += 1
            if attempts < max_attempts:
                # Sleep briefly before retry
                await asyncio.sleep(0.01)

        result = MessageResult(
            message_id=envelope.message_id,
            delivered=delivered,
            acknowledged=acknowledged,
            errors=errors,
            retry_count=max(0, attempts - 1),
        )

        if delivered:
            logger.info(
                EventID.LOG_INFO,
                f"Message {envelope.message_id} delivered successfully",
                component="MessageDispatcher",
            )
        else:
            logger.error(
                EventID.LOG_ERROR,
                f"Message {envelope.message_id} delivery failed: {errors}",
                component="MessageDispatcher",
            )

        return result


class MessageRouter:
    """Matches message destinations across direct, broadcast, role, and capability targets."""

    def __init__(self, agent_manager: AgentManager) -> None:
        self.agent_manager = agent_manager

    def resolve_destinations(
        self,
        receiver_expr: str,
        candidates: list[dict[str, Any]],
    ) -> list[str]:
        """Resolve a routing expression down to concrete target agent IDs.

        receiver_expr format options:
          - "agent-id" (Direct)
          - "role:Coordinator" (Role-based)
          - "capability:run-code" (Capability-based)
          - "broadcast" (All candidate members)
        """
        if receiver_expr == "broadcast":
            return [c["agent_id"] for c in candidates]

        if receiver_expr.startswith("role:"):
            target_role = receiver_expr.split("role:")[1]
            return [c["agent_id"] for c in candidates if c.get("role") == target_role]

        if receiver_expr.startswith("capability:"):
            target_cap = receiver_expr.split("capability:")[1]
            resolved = []
            for c in candidates:
                aid = c["agent_id"]
                try:
                    agent = self.agent_manager.registry.lookup(aid)
                    supported = getattr(agent, "capabilities", [])
                    if target_cap in supported:
                        resolved.append(aid)
                except Exception:
                    pass
            return resolved

        # Default direct matching
        try:
            self.agent_manager.registry.lookup(receiver_expr)
            return [receiver_expr]
        except Exception:
            pass
        return (
            [receiver_expr]
            if any(c["agent_id"] == receiver_expr for c in candidates)
            else []
        )


class CommunicationBus:
    """Centralized message bus enforcing queue capacity limits, FIFO sequencing, and delivery."""

    def __init__(self, agent_manager: AgentManager) -> None:
        self.agent_manager = agent_manager
        self.dispatcher = MessageDispatcher(agent_manager)
        self.router = MessageRouter(agent_manager)
        self.statistics = CommunicationStatistics()
        self._queues: dict[str, deque[MessageEnvelope]] = {}
        self._sequences: dict[str, int] = {}
        self._received_ids: set[str] = set()

    async def send_message(
        self,
        envelope: MessageEnvelope,
        policy: DeliveryPolicy = DeliveryPolicy.FIRE_AND_FORGET,
        team_candidates: list[dict[str, Any]] | None = None,
    ) -> MessageResult:
        """Route and queue a message for delivery, validating envelope constraints."""
        start_time = time.perf_counter()
        self.statistics.messages_sent += 1

        # 1. Deduplication (Idempotence check)
        if envelope.message_id in self._received_ids:
            return MessageResult(
                message_id=envelope.message_id,
                delivered=True,
                acknowledged=True,
                errors=["Duplicate message detected (Idempotency hit)"],
            )
        self._received_ids.add(envelope.message_id)

        # 2. Sender validation
        try:
            self.agent_manager.registry.lookup(envelope.sender_agent_id)
        except Exception:
            self.statistics.messages_failed += 1
            return MessageResult(
                message_id=envelope.message_id,
                delivered=False,
                errors=[f"Sender agent '{envelope.sender_agent_id}' does not exist."],
            )

        # 3. Resolve receivers
        candidates = team_candidates or []
        receivers = self.router.resolve_destinations(
            envelope.receiver_agent_id, candidates
        )
        if not receivers:
            self.statistics.messages_failed += 1
            return MessageResult(
                message_id=envelope.message_id,
                delivered=False,
                errors=[
                    f"No valid destinations resolved for receiver expression: {envelope.receiver_agent_id}"
                ],
            )

        # 4. Check recipient status (availability & health)
        for rc in receivers:
            try:
                self.agent_manager.registry.lookup(rc)
                m = self.agent_manager.get_metrics(rc)
                if not m.get("agent_availability", True):
                    return MessageResult(
                        message_id=envelope.message_id,
                        delivered=False,
                        errors=[f"Recipient '{rc}' is currently disabled."],
                    )
                if m.get("health_status", "Healthy") != "Healthy":
                    return MessageResult(
                        message_id=envelope.message_id,
                        delivered=False,
                        errors=[f"Recipient '{rc}' is unhealthy."],
                    )
            except Exception:
                return MessageResult(
                    message_id=envelope.message_id,
                    delivered=False,
                    errors=[f"Recipient '{rc}' does not exist in registry."],
                )

        # 5. FIFO sequencing and queue limits
        queue_key = f"{envelope.sender_agent_id}:{envelope.receiver_agent_id}"
        if queue_key not in self._queues:
            self._queues[queue_key] = deque()
            self._sequences[queue_key] = 0

        # Enforce queue limit bounds
        limit = platform_settings.MULTI_AGENT_MAX_QUEUE_SIZE
        if len(self._queues[queue_key]) >= limit:
            self.statistics.messages_failed += 1
            return MessageResult(
                message_id=envelope.message_id,
                delivered=False,
                errors=[
                    f"Delivery queue for path '{queue_key}' is full (Max: {limit})."
                ],
            )

        # Update sequence and wrap envelope
        self._sequences[queue_key] += 1
        seq_num = self._sequences[queue_key]
        envelope = MessageEnvelope(
            message_id=envelope.message_id,
            workflow_id=envelope.workflow_id,
            execution_id=envelope.execution_id,
            session_id=envelope.session_id,
            sender_agent_id=envelope.sender_agent_id,
            receiver_agent_id=envelope.receiver_agent_id,
            correlation_id=envelope.correlation_id,
            timestamp=envelope.timestamp,
            priority=envelope.priority,
            payload=envelope.payload,
            metadata=envelope.metadata,
            message_type=envelope.message_type,
            sequence_number=seq_num,
            ttl=envelope.ttl,
        )

        self._queues[queue_key].append(envelope)
        self.statistics.messages_received += len(receivers)

        # Update utilization metric
        total_queue_items = sum(len(q) for q in self._queues.values())
        self.statistics.queue_utilization = total_queue_items / limit

        # 6. Deliver to resolved receivers
        final_success = True
        accumulated_errors = []
        retries_total = 0

        for rc in receivers:
            # Build target envelope
            target_env = MessageEnvelope(
                message_id=envelope.message_id,
                workflow_id=envelope.workflow_id,
                execution_id=envelope.execution_id,
                session_id=envelope.session_id,
                sender_agent_id=envelope.sender_agent_id,
                receiver_agent_id=rc,
                correlation_id=envelope.correlation_id,
                timestamp=envelope.timestamp,
                priority=envelope.priority,
                payload=envelope.payload,
                metadata=envelope.metadata,
                message_type=envelope.message_type,
                sequence_number=envelope.sequence_number,
                ttl=envelope.ttl,
            )

            res = await self.dispatcher.dispatch(target_env, policy)
            retries_total += res.retry_count
            if not res.delivered:
                final_success = False
                accumulated_errors.extend(res.errors)

        # Pop from sender-receiver pair queue after dispatch completion
        if self._queues[queue_key]:
            self._queues[queue_key].popleft()

        duration = time.perf_counter() - start_time
        # Track statistics
        self.statistics.retries += retries_total
        self.statistics.average_delivery_time = (
            (self.statistics.average_delivery_time + duration) / 2
            if self.statistics.average_delivery_time > 0
            else duration
        )

        if final_success:
            self.statistics.messages_delivered += len(receivers)
            return MessageResult(
                message_id=envelope.message_id,
                delivered=True,
                acknowledged=(policy != DeliveryPolicy.FIRE_AND_FORGET),
                retry_count=retries_total,
            )
        else:
            self.statistics.messages_failed += 1
            return MessageResult(
                message_id=envelope.message_id,
                delivered=False,
                errors=accumulated_errors,
                retry_count=retries_total,
            )
