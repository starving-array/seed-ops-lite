# Developer Guide

This guide provides coding standards, extension details, and testing guidelines for the AI Platform.

---

## 1. Coding Standards
- **Linter**: Enforce rules using Ruff.
- **Formatter**: Strict compliance with Black formatting.
- **Type Checking**: Strict typing validated via MyPy.

---

## 2. Platform Architecture Principles
- **Separation of Concerns**: Modular components targeting specific domains (e.g. `NotificationManager` manages delivery; `ReminderScheduler` schedules retries).
- **No Interface Bypass**: Subsystems (e.g. HITL Intervention Engine) communicate exclusively via established adapters (e.g. `CheckpointManager`).

---

## 3. Extension & Custom Providers
To add custom delivery targets, inherit from the base interface class:
```python
from app.platform.hitl.notifications import BaseNotificationProvider

class SlackNotificationProvider(BaseNotificationProvider):
    def send(self, notification_id: str, notification_type: str, target_id: str, content: str) -> bool:
        # Slack webhook payload code...
        return True
```
