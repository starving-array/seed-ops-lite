# API Reference (Locked v3.0.0-rc1)

This index documents the frozen public APIs and contracts of the AI Platform.

---

## 1. Approval Engine (`app.platform.hitl.engine`)

### `ApprovalEngine`
- `create_session(approval_id: str, request: ApprovalRequest) -> ApprovalSession`
- `submit_decision(approval_id: str, decision: ApprovalDecision) -> ApprovalSession`
- `get_session(approval_id: str) -> ApprovalSession`

---

## 2. Intervention Engine (`app.platform.hitl.intervention`)

### `InterventionEngine`
- `process_intervention(request: InterventionRequest) -> bool`
- `get_history(limit: int = 100) -> List[InterventionHistoryEntry]`

---

## 3. Notifications (`app.platform.hitl.notifications`)

### `NotificationManager`
- `create_notification(request: NotificationRequest) -> str | None`
- `send_pending() -> int`
- `acknowledge_notification(notification_id: str) -> bool`
- `cancel_notification(notification_id: str) -> bool`
- `get_metrics() -> NotificationStatistics`
