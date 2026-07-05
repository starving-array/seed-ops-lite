# Configuration Reference (Locked v3.0.0-rc1)

The following configurations are dynamically loaded from `PlatformSettings` without hardcoding:

- `HITL_DEFAULT_EXPIRATION_SECONDS` (Default: `86400.0`): Max duration allowed for reviewers to submit consensus votes.
- `HITL_PAUSE_TIMEOUT_SECONDS` (Default: `3600.0`): Timeout limit for paused workflow states.
- `HITL_RESUME_TIMEOUT_SECONDS` (Default: `3600.0`): Timeout limit for resuming states.
- `HITL_MAX_INTERVENTION_HISTORY` (Default: `1000`): Capped database rows for history log entries.
- `HITL_CHECKPOINT_RESTART_TIMEOUT_SECONDS` (Default: `600.0`): Timeout window for executing stage restart.
- `HITL_REMINDER_INTERVAL_SECONDS` (Default: `300.0`): The base delta seconds between sequential reminder ticks.
- `HITL_MAX_REMINDERS` (Default: `5`): Maximum reminder attempts.
- `HITL_ESCALATION_TIMEOUT_SECONDS` (Default: `1800.0`): Overdue threshold before escalations trigger.
- `HITL_NOTIFICATION_RETENTION_DAYS` (Default: `30`): Database retention cleanup window.
