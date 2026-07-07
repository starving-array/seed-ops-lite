"""LLM telemetry persistence service.

Writes every gateway execution record (success and failure) to SQLite.
Called from LLMGateway after each request attempt.
"""

import contextlib
import datetime
import uuid
from typing import Any


def persist_llm_telemetry(record: dict[str, Any]) -> None:
    """Persist an LLM telemetry record to SQLite.

    Args:
        record: Telemetry dictionary from LLMGateway (success or failure).
    """
    with contextlib.suppress(Exception):
        from app.platform.providers.sqlite_db import sqlite_db_manager
        from app.platform.providers.sqlite_models import LLMTelemetry

        if not sqlite_db_manager._engine:
            return

        entry = LLMTelemetry(
            id=str(uuid.uuid4()),
            timestamp=datetime.datetime.utcnow(),
            provider=record.get("provider") or "unknown",
            model=record.get("model") or "unknown",
            operation=record.get("skill_name") or record.get("template_name"),
            task_id=record.get("correlation_id"),
            request_id=record.get("request_id"),
            correlation_id=record.get("correlation_id"),
            prompt_tokens=record.get("prompt_tokens"),
            completion_tokens=record.get("completion_tokens"),
            total_tokens=record.get("total_tokens"),
            estimated_cost=record.get("estimated_cost"),
            latency_ms=record.get("latency_ms"),
            retry_count=record.get("retry_count") or 0,
            status=record.get("status", "success").lower(),
            error_message=record.get("error_message"),
        )

        with sqlite_db_manager.session() as session:
            session.add(entry)
