from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    """Platform-level configuration details for persistence, runtime, and maintenance."""

    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_",
        case_sensitive=False,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # SQLite Database Configs
    SQLITE_DB_PATH: str = "storage/database.sqlite"
    SQLITE_POOL_SIZE: int = 5
    SQLITE_TIMEOUT_SECONDS: float = 15.0

    # Dataset Storage Folder Configs
    DATASETS_DIR: str = "storage/datasets"
    EXPORTS_DIR: str = "storage/exports"

    # Retention Limits
    DATASET_RETENTION_HOURS: int = 24
    EXPORT_RETENTION_HOURS: int = 24
    PREVIEW_CACHE_RETENTION_HOURS: int = 2

    # Provider Selections
    PERSISTENCE_PROVIDER: str = "sqlite"  # 'sqlite' | 'memory' | 'postgres'
    RUNTIME_PROVIDER: str = "redis"  # 'redis' | 'memory'
    ARTIFACT_PROVIDER: str = "local_disk"  # 'local_disk' | 's3' | 'gcs'

    # Runtime Provider Settings
    RUNTIME_REDIS_HOST: str = "localhost"
    RUNTIME_REDIS_PORT: int = 6379
    RUNTIME_REDIS_PASSWORD: str | None = None
    RUNTIME_REDIS_TIMEOUT_SECONDS: float = 5.0
    RUNTIME_REDIS_MAX_CONNECTIONS: int = 10

    # Reconnection & Heartbeat Poll Intervals
    RUNTIME_RECONNECT_INTERVAL_SECONDS: float = 5.0
    RUNTIME_HEALTH_POLL_INTERVAL_SECONDS: float = 10.0
    RUNTIME_MEMORY_FALLBACK_ENABLED: bool = True

    # Externalized Resilience Settings
    RUNTIME_CACHE_SYNC_QUEUE_SIZE: int = Field(
        default=1000,
        validation_alias=AliasChoices(
            "platform_runtime_cache_sync_queue_size",
            "runtime_cache_sync_queue_size",
        ),
    )
    RUNTIME_QUEUE_WARNING_PERCENT: int = Field(
        default=80,
        validation_alias=AliasChoices(
            "platform_runtime_queue_warning_percent",
            "runtime_queue_warning_percent",
        ),
    )
    RUNTIME_SYNC_BATCH_SIZE: int = Field(
        default=50,
        validation_alias=AliasChoices(
            "platform_runtime_sync_batch_size",
            "runtime_sync_batch_size",
        ),
    )
    RUNTIME_SYNC_RETRY_INTERVAL_SECONDS: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "platform_runtime_sync_retry_interval_seconds",
            "runtime_sync_retry_interval_seconds",
        ),
    )
    RUNTIME_SYNC_MAX_RETRIES: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "platform_runtime_sync_max_retries",
            "runtime_sync_max_retries",
        ),
    )
    RUNTIME_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "platform_runtime_circuit_breaker_failure_threshold",
            "runtime_circuit_breaker_failure_threshold",
        ),
    )
    RUNTIME_CIRCUIT_BREAKER_RECOVERY_SECONDS: float = Field(
        default=0.0,
        validation_alias=AliasChoices(
            "platform_runtime_circuit_breaker_recovery_seconds",
            "runtime_circuit_breaker_recovery_seconds",
        ),
    )
    RUNTIME_HALF_OPEN_MAX_PROBES: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "platform_runtime_half_open_max_probes",
            "runtime_half_open_max_probes",
        ),
    )
    RUNTIME_RECOVERY_POLL_INTERVAL_SECONDS: float = Field(
        default=5.0,
        validation_alias=AliasChoices(
            "platform_runtime_recovery_poll_interval_seconds",
            "runtime_recovery_poll_interval_seconds",
        ),
    )
    RUNTIME_WORKER_SHUTDOWN_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "platform_runtime_worker_shutdown_timeout_seconds",
            "runtime_worker_shutdown_timeout_seconds",
        ),
    )
    RUNTIME_QUEUE_MAX_EVENT_AGE_SECONDS: float = Field(
        default=86400.0,
        validation_alias=AliasChoices(
            "platform_runtime_queue_max_event_age_seconds",
            "runtime_queue_max_event_age_seconds",
        ),
    )
    RUNTIME_REDIS_PING_TIMEOUT_SECONDS: float = Field(
        default=2.0,
        validation_alias=AliasChoices(
            "platform_runtime_redis_ping_timeout_seconds",
            "runtime_redis_ping_timeout_seconds",
        ),
    )
    RUNTIME_SYNC_MAX_CONCURRENT_TASKS: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "platform_runtime_sync_max_concurrent_tasks",
            "runtime_sync_max_concurrent_tasks",
        ),
    )
    RUNTIME_CACHE_DEFAULT_TTL_SECONDS: int = Field(
        default=3600,
        validation_alias=AliasChoices(
            "platform_runtime_cache_default_ttl_seconds",
            "runtime_cache_default_ttl_seconds",
        ),
    )
    RUNTIME_MEMORY_CACHE_MAX_ENTRIES: int = Field(
        default=10000,
        validation_alias=AliasChoices(
            "platform_runtime_memory_cache_max_entries",
            "runtime_memory_cache_max_entries",
        ),
    )
    RUNTIME_MEMORY_EVICTION_BATCH_SIZE: int = Field(
        default=100,
        validation_alias=AliasChoices(
            "platform_runtime_memory_eviction_batch_size",
            "runtime_memory_eviction_batch_size",
        ),
    )
    RUNTIME_MEMORY_CLEANUP_INTERVAL_SECONDS: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "platform_runtime_memory_cleanup_interval_seconds",
            "runtime_memory_cleanup_interval_seconds",
        ),
    )

    # Tool Framework Configurations
    TOOLS_MAX_EXECUTION_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "platform_tools_max_execution_timeout_seconds",
            "tools_max_execution_timeout_seconds",
        ),
    )
    TOOLS_MAX_CONCURRENT_EXECUTIONS: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "platform_tools_max_concurrent_executions",
            "tools_max_concurrent_executions",
        ),
    )
    TOOLS_MAX_RETRIES: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "platform_tools_max_retries",
            "tools_max_retries",
        ),
    )
    TOOLS_MAX_EXPORT_SIZE: int = Field(
        default=1048576,
        validation_alias=AliasChoices(
            "platform_tools_max_export_size",
            "tools_max_export_size",
        ),
    )
    TOOLS_MAX_SEARCH_RESULTS: int = Field(
        default=100,
        validation_alias=AliasChoices(
            "platform_tools_max_search_results",
            "tools_max_search_results",
        ),
    )
    TOOLS_MAX_DOCUMENT_SIZE: int = Field(
        default=1048576,
        validation_alias=AliasChoices(
            "platform_tools_max_document_size",
            "tools_max_document_size",
        ),
    )
    PLANNING_MAX_DEPTH: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "platform_planning_max_depth",
            "planning_max_depth",
        ),
    )
    PLANNING_MAX_TASKS: int = Field(
        default=50,
        validation_alias=AliasChoices(
            "platform_planning_max_tasks",
            "planning_max_tasks",
        ),
    )
    PLANNING_MAX_DEPENDENCY_DEPTH: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "platform_planning_max_dependency_depth",
            "planning_max_dependency_depth",
        ),
    )
    PLANNING_MAX_BRANCHING_FACTOR: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "platform_planning_max_branching_factor",
            "planning_max_branching_factor",
        ),
    )
    SCHEDULER_MAX_DEPTH: int = Field(
        default=15,
        validation_alias=AliasChoices(
            "platform_scheduler_max_depth",
            "scheduler_max_depth",
        ),
    )
    SCHEDULER_MAX_STAGES: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "platform_scheduler_max_stages",
            "scheduler_max_stages",
        ),
    )
    SCHEDULER_MAX_PARALLEL_TASKS: int = Field(
        default=8,
        validation_alias=AliasChoices(
            "platform_scheduler_max_parallel_tasks",
            "scheduler_max_parallel_tasks",
        ),
    )
    ORCHESTRATOR_TIMEOUT_SECONDS: float = Field(
        default=300.0,
        validation_alias=AliasChoices(
            "platform_orchestrator_timeout_seconds",
            "orchestrator_timeout_seconds",
        ),
    )
    ORCHESTRATOR_EVENT_QUEUE_CAPACITY: int = Field(
        default=100,
        validation_alias=AliasChoices(
            "platform_orchestrator_event_queue_capacity",
            "orchestrator_event_queue_capacity",
        ),
    )
    ORCHESTRATOR_MAX_ACTIVE_SESSIONS: int = Field(
        default=10,
        validation_alias=AliasChoices(
            "platform_orchestrator_max_active_sessions",
            "orchestrator_max_active_sessions",
        ),
    )
    INTEGRATION_SYNC_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "platform_integration_sync_timeout_seconds",
            "integration_sync_timeout_seconds",
        ),
    )
    INTEGRATION_MAX_RETRIES: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "platform_integration_max_retries",
            "integration_max_retries",
        ),
    )
    INTEGRATION_HEALTH_INTERVAL_SECONDS: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "platform_integration_health_interval_seconds",
            "integration_health_interval_seconds",
        ),
    )
    RECOVERY_MAX_ATTEMPTS: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "platform_recovery_max_attempts",
            "recovery_max_attempts",
        ),
    )
    RECOVERY_CHECKPOINT_FREQUENCY: int = Field(
        default=1,
        validation_alias=AliasChoices(
            "platform_recovery_checkpoint_frequency",
            "recovery_checkpoint_frequency",
        ),
    )
    RECOVERY_CANCELLATION_TIMEOUT_SECONDS: float = Field(
        default=15.0,
        validation_alias=AliasChoices(
            "platform_recovery_cancellation_timeout_seconds",
            "recovery_cancellation_timeout_seconds",
        ),
    )
    RECOVERY_TIMEOUT_SECONDS: float = Field(
        default=60.0,
        validation_alias=AliasChoices(
            "platform_recovery_timeout_seconds",
            "recovery_timeout_seconds",
        ),
    )
    RECOVERY_RETRY_DELAY_SECONDS: float = Field(
        default=2.0,
        validation_alias=AliasChoices(
            "platform_recovery_retry_delay_seconds",
            "recovery_retry_delay_seconds",
        ),
    )


platform_settings = PlatformSettings()
