# Issue Log — SafeSeedOps Lite

This document records all anomalies, bugs, configuration issues, or dependencies mismatch discovered during validation audits.

---

## Active & Resolved Issue Audits

### **Issue ID**: `ISSUE-001`
*   **Title**: `TypeError` in `structlog` ProcessorFormatter during server startup
*   **Location**: [`app/core/logging/logging.py`](/app/core/logging/logging.py)
*   **Severity**: Critical (Blocker)
*   **Priority**: High
*   **Steps to Reproduce**:
    1.  Install dependencies using `uv sync`.
    2.  Start the FastAPI application:
        ```bash
        uv run uvicorn app.main:app --reload
        ```
    3.  Observe immediate application exit during startup lifecycle context initialization.
*   **Expected Behavior**: FastAPI application starts uvicorn process and initializes lifespans.
*   **Actual Behavior**: Exits with:
    `TypeError: Formatter.__init__() got an unexpected keyword argument 'foreign_pre_processors'`
*   **Root Cause**: The installed version of the `structlog` library has deprecated/renamed `foreign_pre_processors` to `foreign_pre_chain`.
*   **Suggested Fix**: Update line 77 in `app/core/logging/logging.py` to use `foreign_pre_chain=shared_processors`.
*   **Status**: **Closed** (Resolved and committed in `57e48de`).

---

### **Issue ID**: `ISSUE-002`
*   **Title**: AI Schema Assistant fails gracefully when `GEMINI_API_KEY` is missing
*   **Location**: [`app/api/endpoints/schema.py`](/app/api/endpoints/schema.py)
*   **Severity**: Medium
*   **Priority**: Medium
*   **Steps to Reproduce**:
    1.  Leave `GEMINI_API_KEY` empty in `.env`.
    2.  Navigate to **Schema Validation** workspace.
    3.  Click **Ask AI Assistant**.
*   **Expected Behavior**: Displays warning to user explaining that Gemini API is missing.
*   **Actual Behavior**: Validation displays `"AI Schema Assistant is currently unavailable: Gemini API key is not configured."` and does not crash the CLI/API.
*   **Root Cause**: The system catches exceptions in the validation agent, which prevents a backend crash but leaves the feature disabled.
*   **Suggested Fix**: (Optional) Add a pre-check validation warning in the UI if the backend reports `GEMINI_API_KEY` is empty.
*   **Status**: **Open** (Gracefully handled fallback).
