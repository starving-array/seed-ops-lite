"""Human-in-the-Loop (HITL) Notifications & Escalation Framework."""

import json
import sqlite3
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging.logging import logger
from app.platform.configuration.settings import platform_settings
from app.platform.providers.sqlite import DomainEventDispatcher
from app.platform.providers.sqlite_db import sqlite_db_manager
from app.telemetry.events import EventID


# Interfaces
class BaseNotificationProvider:
    """Interface to keep delivery provider-agnostic."""

    def send(
        self,
        notification_id: str,
        notification_type: str,
        target_id: str,
        content: str,
    ) -> bool:
        """Deliver notification payload to the target destination."""
        raise NotImplementedError("Delivery providers must implement this method.")


class MockNotificationProvider(BaseNotificationProvider):
    """Provider-agnostic mock delivery target."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    def send(
        self,
        notification_id: str,
        notification_type: str,
        target_id: str,
        content: str,
    ) -> bool:
        self.sent_messages.append(
            {
                "notification_id": notification_id,
                "notification_type": notification_type,
                "target_id": target_id,
                "content": content,
                "timestamp": time.time(),
            }
        )
        return True


# Enums
class NotificationType(str, Enum):
    """Supported workflow notification lifecycle categories."""

    APPROVAL_REQUESTED = "Approval Requested"
    REMINDER = "Reminder"
    ESCALATION = "Escalation"
    APPROVAL_COMPLETED = "Approval Completed"
    APPROVAL_REJECTED = "Approval Rejected"
    APPROVAL_EXPIRED = "Approval Expired"
    EXECUTION_PAUSED = "Execution Paused"
    EXECUTION_RESUMED = "Execution Resumed"
    EXECUTION_CANCELLED = "Execution Cancelled"


class EscalationPolicy(str, Enum):
    """Rules dictating escalation chains for overdue workflows."""

    NO_ESCALATION = "NO_ESCALATION"
    ESCALATE_TO_MANAGER = "ESCALATE_TO_MANAGER"
    ESCALATE_TO_GROUP = "ESCALATE_TO_GROUP"
    ESCALATE_TO_ADMIN = "ESCALATE_TO_ADMIN"
    AUTO_EXPIRE = "AUTO_EXPIRE"


class ReminderPolicy(str, Enum):
    """Types of reminder recurrence and schedules."""

    SINGLE_REMINDER = "Single Reminder"
    FIXED_INTERVAL = "Fixed Interval"
    EXPONENTIAL_BACKOFF = "Exponential Backoff"


class DeliveryState(str, Enum):
    """Delivery and lifecycle status for a notification instance."""

    PENDING = "Pending"
    SCHEDULED = "Scheduled"
    SENT = "Sent"
    ACKNOWLEDGED = "Acknowledged"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"
    FAILED = "Failed"


# Models
class NotificationRequest(BaseModel):
    """Pydantic model representing a notification payload request."""

    model_config = ConfigDict(frozen=True)

    approval_id: str = Field(..., description="Target approval workflow ID.")
    notification_type: NotificationType = Field(
        ..., description="Classification category."
    )
    target_id: str = Field(..., description="Target reviewer or destination ID.")
    content: str = Field(..., description="Formatted message content.")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata parameters."
    )


class NotificationLogEntry(BaseModel):
    """Database representation of a recorded notification."""

    model_config = ConfigDict(frozen=True)

    notification_id: str = Field(..., description="Unique notification ID.")
    approval_id: str = Field(..., description="Associated approval ID.")
    notification_type: str = Field(..., description="Type of notification.")
    target_id: str = Field(..., description="Destination destination ID.")
    delivery_state: str = Field(..., description="Current delivery state status.")
    scheduled_at: float = Field(..., description="Scheduled epoch time.")
    sent_at: float | None = Field(default=None, description="Actual sent epoch time.")
    acknowledged_at: float | None = Field(
        default=None, description="Acknowledgement epoch time."
    )
    expired_at: float | None = Field(default=None, description="Expiration epoch time.")
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)


class NotificationStatistics(BaseModel):
    """Aggregated metrics for the notifications framework."""

    notifications_created: int = 0
    notifications_sent: int = 0
    acknowledgements: int = 0
    escalations: int = 0
    expired_notifications: int = 0
    reminder_count: int = 0
    average_delivery_delay: float = 0.0
    average_acknowledgement_time: float = 0.0


# Initialize SQLite Tables
def init_notifications_table() -> None:
    """Ensure notifications SQLite tables are initialized."""
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_notifications (
                notification_id TEXT PRIMARY KEY,
                approval_id TEXT,
                notification_type TEXT,
                target_id TEXT,
                delivery_state TEXT,
                scheduled_at REAL,
                sent_at REAL,
                acknowledged_at REAL,
                expired_at REAL,
                retry_count INTEGER,
                max_retries INTEGER,
                metadata TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class NotificationManager:
    """Governs delivery rules, acknowledgment tracking, and persistence logic."""

    def __init__(self, provider: BaseNotificationProvider | None = None) -> None:
        self.provider = provider or MockNotificationProvider()
        init_notifications_table()

    def create_notification(self, request: NotificationRequest) -> str | None:
        """Validate, generate, and record a new workflow notification."""
        # 1. Validation
        if not request.target_id:
            logger.warning(
                EventID.LOG_WARNING,
                "Notification rejected: missing delivery target",
                component="NotificationManager",
            )
            return None

        is_valid = True
        reject_reason = ""

        # Validate Approval existence
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='approval_sessions'"
            )
            if cursor.fetchone()[0] > 0:
                cursor.execute(
                    "SELECT count(*) FROM approval_sessions WHERE approval_id = ?",
                    (request.approval_id,),
                )
                if cursor.fetchone()[0] == 0:
                    is_valid = False
                    reject_reason = f"approval '{request.approval_id}' does not exist"
            elif request.metadata.get("bypass_approval_check") is not True:
                is_valid = False
                reject_reason = "approval table not initialized"

            # Duplicate prevention check
            if is_valid:
                cursor.execute(
                    "SELECT metadata FROM workflow_notifications WHERE approval_id = ? AND notification_type = ? AND target_id = ? AND delivery_state IN (?, ?)",
                    (
                        request.approval_id,
                        request.notification_type.value,
                        request.target_id,
                        DeliveryState.PENDING.value,
                        DeliveryState.SCHEDULED.value,
                    ),
                )
                rows = cursor.fetchall()
                for r in rows:
                    meta = json.loads(r[0]) if r[0] else {}
                    if request.notification_type == NotificationType.REMINDER:
                        if meta.get("reminder_index") == request.metadata.get(
                            "reminder_index"
                        ):
                            is_valid = False
                            reject_reason = "duplicate reminder detected"
                            break
                    elif request.notification_type == NotificationType.ESCALATION:
                        if meta.get("escalation_policy") == request.metadata.get(
                            "escalation_policy"
                        ):
                            is_valid = False
                            reject_reason = "duplicate escalation detected"
                            break
                    else:
                        is_valid = False
                        reject_reason = "duplicate notification detected"
                        break
        finally:
            conn.close()

        if not is_valid:
            logger.warning(
                EventID.LOG_WARNING,
                f"Notification rejected: {reject_reason}",
                component="NotificationManager",
            )
            return None

        # Save to DB
        import uuid

        notification_id = str(uuid.uuid4())
        scheduled_at = time.time()
        self._save_log(notification_id, request, DeliveryState.PENDING, scheduled_at)

        logger.info(
            EventID.LOG_INFO,
            f"Notification created: {notification_id}",
            component="NotificationManager",
        )
        DomainEventDispatcher.dispatch(
            "NotificationCreated",
            {
                "notification_id": notification_id,
                "approval_id": request.approval_id,
                "type": request.notification_type.value,
            },
        )
        return notification_id

    def send_pending(self) -> int:
        """Trigger delivery for pending notification requests."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        sent_count = 0
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT notification_id, approval_id, notification_type, target_id, retry_count, max_retries, metadata FROM workflow_notifications WHERE delivery_state = ?",
                (DeliveryState.PENDING.value,),
            )
            rows = cursor.fetchall()
            for r in rows:
                nid, approval_id, ntype, target, retry, max_retry, metadata_str = r
                metadata = json.loads(metadata_str) if metadata_str else {}
                content = metadata.get("content", "Workflow notification trigger.")

                # Validate max retries
                if retry >= max_retry:
                    cursor.execute(
                        "UPDATE workflow_notifications SET delivery_state = ? WHERE notification_id = ?",
                        (DeliveryState.FAILED.value, nid),
                    )
                    conn.commit()
                    continue

                # Delivery attempt
                success = self.provider.send(nid, ntype, target, content)
                sent_at = time.time()
                if success:
                    cursor.execute(
                        "UPDATE workflow_notifications SET delivery_state = ?, sent_at = ? WHERE notification_id = ?",
                        (DeliveryState.SENT.value, sent_at, nid),
                    )
                    conn.commit()
                    sent_count += 1
                    logger.info(
                        EventID.LOG_INFO,
                        f"Notification sent: {nid}",
                        component="NotificationManager",
                    )
                    DomainEventDispatcher.dispatch(
                        "NotificationSent",
                        {"notification_id": nid, "approval_id": approval_id},
                    )
                else:
                    cursor.execute(
                        "UPDATE workflow_notifications SET retry_count = retry_count + 1 WHERE notification_id = ?",
                        (nid,),
                    )
                    conn.commit()
        finally:
            conn.close()
        return sent_count

    def acknowledge_notification(self, notification_id: str) -> bool:
        """Record human reviewer response/acknowledgment."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT delivery_state, sent_at FROM workflow_notifications WHERE notification_id = ?",
                (notification_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            state, sent_at = row
            if state != DeliveryState.SENT.value:
                return False

            ack_at = time.time()
            cursor.execute(
                "UPDATE workflow_notifications SET delivery_state = ?, acknowledged_at = ? WHERE notification_id = ?",
                (DeliveryState.ACKNOWLEDGED.value, ack_at, notification_id),
            )
            conn.commit()
            logger.info(
                EventID.LOG_INFO,
                f"Notification acknowledged: {notification_id}",
                component="NotificationManager",
            )
            DomainEventDispatcher.dispatch(
                "NotificationAcknowledged", {"notification_id": notification_id}
            )
            return True
        finally:
            conn.close()

    def cancel_notification(self, notification_id: str) -> bool:
        """Cancel an scheduled notification."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT delivery_state FROM workflow_notifications WHERE notification_id = ?",
                (notification_id,),
            )
            row = cursor.fetchone()
            if not row or row[0] in (
                DeliveryState.ACKNOWLEDGED.value,
                DeliveryState.CANCELLED.value,
            ):
                return False

            cursor.execute(
                "UPDATE workflow_notifications SET delivery_state = ? WHERE notification_id = ?",
                (DeliveryState.CANCELLED.value, notification_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def get_metrics(self) -> NotificationStatistics:
        """Compile and calculate notifications metrics."""
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        stats = NotificationStatistics()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM workflow_notifications")
            stats.notifications_created = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_notifications WHERE sent_at IS NOT NULL"
            )
            stats.notifications_sent = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_notifications WHERE delivery_state = ?",
                (DeliveryState.ACKNOWLEDGED.value,),
            )
            stats.acknowledgements = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_notifications WHERE notification_type = ?",
                (NotificationType.ESCALATION.value,),
            )
            stats.escalations = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_notifications WHERE delivery_state = ?",
                (DeliveryState.EXPIRED.value,),
            )
            stats.expired_notifications = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM workflow_notifications WHERE notification_type = ?",
                (NotificationType.REMINDER.value,),
            )
            stats.reminder_count = cursor.fetchone()[0]

            # Timing calculations
            cursor.execute(
                "SELECT scheduled_at, sent_at, acknowledged_at FROM workflow_notifications"
            )
            rows = cursor.fetchall()
            delays = []
            ack_times = []
            for sched, sent, ack in rows:
                if sent is not None:
                    delays.append(sent - sched)
                if sent is not None and ack is not None:
                    ack_times.append(ack - sent)

            stats.average_delivery_delay = sum(delays) / len(delays) if delays else 0.0
            stats.average_acknowledgement_time = (
                sum(ack_times) / len(ack_times) if ack_times else 0.0
            )
        finally:
            conn.close()
        return stats

    def _save_log(
        self,
        notification_id: str,
        req: NotificationRequest,
        state: DeliveryState,
        scheduled_at: float,
    ) -> None:
        db_path = sqlite_db_manager.db_path
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            metadata = {**req.metadata, "content": req.content}
            cursor.execute(
                """
                INSERT INTO workflow_notifications (
                    notification_id, approval_id, notification_type, target_id, delivery_state, scheduled_at, sent_at, acknowledged_at, expired_at, retry_count, max_retries, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification_id,
                    req.approval_id,
                    req.notification_type.value,
                    req.target_id,
                    state.value,
                    scheduled_at,
                    None,
                    None,
                    None,
                    0,
                    3,
                    json.dumps(metadata),
                ),
            )
            conn.commit()
        finally:
            conn.close()


class ReminderScheduler:
    """Manages reminder recurrence rules, exponential backoff, and expiration triggers."""

    def __init__(self, manager: NotificationManager) -> None:
        self.manager = manager

    def schedule_reminder(
        self,
        approval_id: str,
        target_id: str,
        policy: ReminderPolicy,
        reminder_count: int,
        base_interval: float = 300.0,
    ) -> str | None:
        """Schedule and create a new reminder notification based on selected policies."""
        if reminder_count >= platform_settings.HITL_MAX_REMINDERS:
            logger.warning(
                EventID.LOG_WARNING,
                f"Reminder limits hit for approval: {approval_id}",
                component="ReminderScheduler",
            )
            return None

        # Backoff timing checks
        interval = base_interval
        if policy == ReminderPolicy.EXPONENTIAL_BACKOFF:
            interval = base_interval * (2**reminder_count)

        if interval < 0:
            raise ValueError("Reminder interval cannot be negative.")

        scheduled_time = time.time() + interval

        req = NotificationRequest(
            approval_id=approval_id,
            notification_type=NotificationType.REMINDER,
            target_id=target_id,
            content=f"Reminder check: overdue approval action {approval_id}.",
            metadata={
                "bypass_approval_check": True,
                "scheduled_time": scheduled_time,
                "reminder_index": reminder_count,
            },
        )
        nid = self.manager.create_notification(req)
        if nid:
            logger.info(
                EventID.LOG_INFO,
                f"Reminder scheduled: {nid} for time {scheduled_time}",
                component="ReminderScheduler",
            )
        return nid


class EscalationManager:
    """Orchestrates escalation policies and overdue workflow alerts."""

    def __init__(self, manager: NotificationManager) -> None:
        self.manager = manager

    def check_and_escalate(
        self,
        approval_id: str,
        policy: EscalationPolicy,
        created_at: float,
        target_group: str | None = None,
    ) -> bool:
        """Trigger escalation procedures for workflows exceeding configured timeout limits."""
        timeout = platform_settings.HITL_ESCALATION_TIMEOUT_SECONDS
        if time.time() - created_at < timeout:
            return False

        if policy == EscalationPolicy.NO_ESCALATION:
            return False

        # Expiry escalation logic
        if policy == EscalationPolicy.AUTO_EXPIRE:
            logger.info(
                EventID.LOG_INFO,
                f"Escalation expired for approval: {approval_id}",
                component="EscalationManager",
            )
            DomainEventDispatcher.dispatch(
                "ApprovalExpired", {"approval_id": approval_id}
            )
            return True

        # Escalate target resolution
        escalation_target = "system_admin"
        if policy == EscalationPolicy.ESCALATE_TO_MANAGER:
            escalation_target = "manager_group"
        elif policy == EscalationPolicy.ESCALATE_TO_GROUP:
            escalation_target = target_group or "reviewer_group"
        elif policy == EscalationPolicy.ESCALATE_TO_ADMIN:
            escalation_target = "admin_group"

        req = NotificationRequest(
            approval_id=approval_id,
            notification_type=NotificationType.ESCALATION,
            target_id=escalation_target,
            content=f"CRITICAL Escalation alert for approval {approval_id}.",
            metadata={"bypass_approval_check": True, "escalation_policy": policy.value},
        )
        nid = self.manager.create_notification(req)
        if nid:
            logger.info(
                EventID.LOG_INFO,
                f"Escalation triggered: {nid} targeting {escalation_target}",
                component="EscalationManager",
            )
            DomainEventDispatcher.dispatch(
                "EscalationTriggered",
                {"approval_id": approval_id, "notification_id": nid},
            )
            return True
        return False
