# Changelog

All notable changes to this project will be documented in this file.

## [3.0.0-rc1] - 2026-07-05

### Added
- Added **Human-in-the-Loop (HITL) Platform** including:
  - **Approval Workflow Engine** supporting reviewer consensus (`ANY_REVIEWER`, `ALL_REVIEWERS`, `MAJORITY`).
  - **Intervention Engine** enabling workflow executions to pause, resume, cancel, or restart from stage checkpoint.
  - **Notification & Escalation Framework** supporting exponential backoff reminders and timeout-based escalations.
- Complete performance benchmark, load stress, and chaos engineering verification suites.
