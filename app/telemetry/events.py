"""Strongly-typed system event catalog definitions."""

from enum import Enum

from pydantic import BaseModel, Field


class EventID(str, Enum):
    """Enumeration of system-wide event identifier codes."""

    # APP Namespace
    APP_STARTED = "APP-1001"
    APP_STOPPED = "APP-1002"

    # HTTP Namespace
    HTTP_RECEIVED = "HTTP-1001"
    HTTP_COMPLETED = "HTTP-1002"

    # REDIS Namespace
    REDIS_CONNECTED = "REDIS-1001"
    REDIS_DISCONNECTED = "REDIS-1002"

    # LOG Namespace
    LOG_INFO = "LOG-1001"
    LOG_WARNING = "LOG-1002"
    LOG_ERROR = "LOG-1003"

    # ==========================================================================
    # Reserved Namespaces for Future Engines
    # ==========================================================================

    # JOB Namespace
    JOB_CREATED = "JOB-1001"
    JOB_STARTED = "JOB-1002"
    JOB_COMPLETED = "JOB-1003"
    JOB_FAILED = "JOB-1004"

    # WORKER Namespace
    WORKER_STARTED = "WORKER-1001"
    WORKER_STOPPED = "WORKER-1002"
    WORKER_HEARTBEAT = "WORKER-1003"

    # LLM Namespace
    LLM_REQUEST = "LLM-1001"
    LLM_RESPONSE = "LLM-1002"
    LLM_ERROR = "LLM-1003"

    # GUARDIAN Namespace
    GUARDIAN_CHECK_PASSED = "GUARDIAN-1001"
    GUARDIAN_CHECK_FAILED = "GUARDIAN-1002"

    # BINDING Namespace
    BINDING_RESOLVED = "BINDING-1001"
    BINDING_FAILED = "BINDING-1002"

    # EXPORT Namespace
    EXPORT_STARTED = "EXPORT-1001"
    EXPORT_COMPLETED = "EXPORT-1002"
    EXPORT_FAILED = "EXPORT-1003"

    # GENERATION Namespace
    GENERATION_STARTED = "GEN-1001"
    GENERATION_COMPLETED = "GEN-1002"
    GENERATION_FAILED = "GEN-1003"

    # SQLITE Namespace
    SQLITE_CONNECTED = "SQLITE-1001"
    SQLITE_MIGRATED = "SQLITE-1002"
    SQLITE_FAILED = "SQLITE-1003"

    # RUNTIME Namespace (memory / fallback transitions)
    RUNTIME_MEMORY_ACTIVATED = "RUNTIME-1001"
    RUNTIME_REDIS_RECOVERED = "RUNTIME-1002"
    RUNTIME_REDIS_LOST = "RUNTIME-1003"
    RUNTIME_INITIALIZED = "RUNTIME-1004"

    # CARETAKER Namespace
    CARETAKER_STARTED = "CARETAKER-1001"
    CARETAKER_COMPLETED = "CARETAKER-1002"
    CARETAKER_FAILED = "CARETAKER-1003"

    # PERF Namespace (slow-operation warnings)
    PERF_SLOW_OPERATION = "PERF-1001"


class TelemetryEvent(BaseModel):
    """Pydantic model representing metadata for an entry in the Event Catalog."""

    event_id: EventID = Field(description="Strongly-typed unique system event ID code")
    name: str = Field(description="Human readable name identifier of the event")
    description: str = Field(
        description="Detailed narrative of what the event represents"
    )
