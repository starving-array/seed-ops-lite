"""Unit and integration tests for the Human-in-the-Loop (HITL) Notifications & Escalation Framework."""

import sqlite3
import time

import pytest

from app.platform.configuration.settings import platform_settings
from app.platform.hitl import (
    DeliveryState,
    EscalationManager,
    EscalationPolicy,
    MockNotificationProvider,
    NotificationManager,
    NotificationRequest,
    NotificationType,
    ReminderPolicy,
    ReminderScheduler,
)
from app.platform.providers.sqlite_db import sqlite_db_manager


@pytest.fixture(autouse=True)
def clean_database_state() -> None:
    """Fixture to ensure tables exist and are clean before each test run."""
    # Instantiating manager triggers table initialization
    _ = NotificationManager()

    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflow_notifications")
        # Ensure approval sessions exist for existence validation checks
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS approval_sessions (approval_id TEXT PRIMARY KEY, status TEXT)"
        )
        cursor.execute("DELETE FROM approval_sessions")
        cursor.execute(
            "INSERT INTO approval_sessions (approval_id, status) VALUES (?, ?)",
            ("app-valid-123", "Pending"),
        )
        conn.commit()
    finally:
        conn.close()


def test_configuration_loading() -> None:
    """Verify notification configuration values load properly from PlatformSettings."""
    assert platform_settings.HITL_REMINDER_INTERVAL_SECONDS == 300.0
    assert platform_settings.HITL_MAX_REMINDERS == 5
    assert platform_settings.HITL_ESCALATION_TIMEOUT_SECONDS == 1800.0
    assert platform_settings.HITL_NOTIFICATION_RETENTION_DAYS == 30


def test_notification_creation_and_sending() -> None:
    """Verify that notifications are created in Pending state and successfully delivered."""
    provider = MockNotificationProvider()
    manager = NotificationManager(provider)

    req = NotificationRequest(
        approval_id="app-valid-123",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="reviewer-1",
        content="Action required on approval 123.",
    )

    nid = manager.create_notification(req)
    assert nid is not None

    # Verify initially PENDING
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT delivery_state, retry_count FROM workflow_notifications WHERE notification_id = ?",
            (nid,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == DeliveryState.PENDING.value
        assert row[1] == 0
    finally:
        conn.close()

    # Trigger sending
    sent_count = manager.send_pending()
    assert sent_count == 1
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0]["notification_id"] == nid

    # Verify updated to SENT
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT delivery_state, sent_at FROM workflow_notifications WHERE notification_id = ?",
            (nid,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == DeliveryState.SENT.value
        assert row[1] is not None
    finally:
        conn.close()


def test_duplicate_notification_prevention() -> None:
    """Verify that scheduling duplicate pending notifications for same target is rejected."""
    manager = NotificationManager()
    req = NotificationRequest(
        approval_id="app-valid-123",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="reviewer-1",
        content="First notification.",
    )

    nid1 = manager.create_notification(req)
    assert nid1 is not None

    # Create duplicate request
    nid2 = manager.create_notification(req)
    assert nid2 is None  # Duplicate rejected


def test_validation_checks() -> None:
    """Verify validation boundaries: missing targets, non-existent approvals, etc."""
    manager = NotificationManager()

    # 1. Missing target
    req_no_target = NotificationRequest(
        approval_id="app-valid-123",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="",
        content="Hello",
    )
    assert manager.create_notification(req_no_target) is None

    # 2. Non-existent approval ID
    req_bad_approval = NotificationRequest(
        approval_id="app-does-not-exist",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="reviewer-1",
        content="Hello",
    )
    assert manager.create_notification(req_bad_approval) is None


def test_acknowledgement_tracking() -> None:
    """Verify acknowledgment changes state from Sent to Acknowledged and logs timestamps."""
    manager = NotificationManager()
    req = NotificationRequest(
        approval_id="app-valid-123",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="reviewer-1",
        content="Track me",
    )
    nid = manager.create_notification(req)
    assert nid is not None

    # Acknowledge before sent -> fails
    assert manager.acknowledge_notification(nid) is False

    manager.send_pending()
    assert manager.acknowledge_notification(nid) is True

    # Check updated state
    db_path = sqlite_db_manager.db_path
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT delivery_state, acknowledged_at FROM workflow_notifications WHERE notification_id = ?",
            (nid,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == DeliveryState.ACKNOWLEDGED.value
        assert row[1] is not None
    finally:
        conn.close()


def test_notification_cancellation() -> None:
    """Verify pending or scheduled notifications can be cancelled."""
    manager = NotificationManager()
    req = NotificationRequest(
        approval_id="app-valid-123",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="reviewer-1",
        content="Cancel me",
    )
    nid = manager.create_notification(req)
    assert nid is not None

    assert manager.cancel_notification(nid) is True

    # Try cancelling again -> fails
    assert manager.cancel_notification(nid) is False


def test_reminder_scheduling() -> None:
    """Verify scheduling reminder with policies (Fixed, backoff, maximum count checks)."""
    manager = NotificationManager()
    scheduler = ReminderScheduler(manager)

    # 1. Fixed interval reminder
    nid = scheduler.schedule_reminder(
        approval_id="app-valid-123",
        target_id="reviewer-1",
        policy=ReminderPolicy.FIXED_INTERVAL,
        reminder_count=0,
        base_interval=300.0,
    )
    assert nid is not None

    # 2. Exponential backoff interval check
    nid_backoff = scheduler.schedule_reminder(
        approval_id="app-valid-123",
        target_id="reviewer-1",
        policy=ReminderPolicy.EXPONENTIAL_BACKOFF,
        reminder_count=2,  # 300 * 2^2 = 1200
        base_interval=300.0,
    )
    assert nid_backoff is not None

    # 3. Maximum reminder count check (rejection)
    nid_limit = scheduler.schedule_reminder(
        approval_id="app-valid-123",
        target_id="reviewer-1",
        policy=ReminderPolicy.FIXED_INTERVAL,
        reminder_count=10,  # Limits is platform_settings.HITL_MAX_REMINDERS (5)
        base_interval=300.0,
    )
    assert nid_limit is None


def test_reminder_interval_negative_validation() -> None:
    """Verify reminder scheduling rejects negative intervals."""
    manager = NotificationManager()
    scheduler = ReminderScheduler(manager)

    with pytest.raises(ValueError, match="Reminder interval cannot be negative"):
        scheduler.schedule_reminder(
            approval_id="app-valid-123",
            target_id="reviewer-1",
            policy=ReminderPolicy.FIXED_INTERVAL,
            reminder_count=0,
            base_interval=-10.0,
        )


def test_escalation_triggering() -> None:
    """Verify escalation checks trigger notification when timeouts occur."""
    manager = NotificationManager()
    escalator = EscalationManager(manager)

    # 1. Below timeout limit -> False
    assert (
        escalator.check_and_escalate(
            approval_id="app-valid-123",
            policy=EscalationPolicy.ESCALATE_TO_ADMIN,
            created_at=time.time(),  # fresh
        )
        is False
    )

    # 2. Exceeds timeout -> True (Escalate to Admin target)
    triggered = escalator.check_and_escalate(
        approval_id="app-valid-123",
        policy=EscalationPolicy.ESCALATE_TO_ADMIN,
        created_at=time.time() - 2000.0,  # exceeds 1800s timeout
    )
    assert triggered is True

    # 3. Auto expire policy trigger
    triggered_expire = escalator.check_and_escalate(
        approval_id="app-valid-123",
        policy=EscalationPolicy.AUTO_EXPIRE,
        created_at=time.time() - 2000.0,
    )
    assert triggered_expire is True


def test_metrics_collection() -> None:
    """Verify that notification statistics accumulate counts and intervals correctly."""
    manager = NotificationManager()
    req = NotificationRequest(
        approval_id="app-valid-123",
        notification_type=NotificationType.APPROVAL_REQUESTED,
        target_id="reviewer-1",
        content="Stats test",
    )
    nid = manager.create_notification(req)
    assert nid is not None

    manager.send_pending()
    manager.acknowledge_notification(nid)

    metrics = manager.get_metrics()
    assert metrics.notifications_created == 1
    assert metrics.notifications_sent == 1
    assert metrics.acknowledgements == 1
    assert metrics.average_delivery_delay >= 0.0
