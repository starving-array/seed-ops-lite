from pydantic_settings import BaseSettings, SettingsConfigDict


class PlatformSettings(BaseSettings):
    """Platform-level configuration details for persistence, runtime, and maintenance."""

    model_config = SettingsConfigDict(
        env_prefix="PLATFORM_",
        case_sensitive=False,
        extra="ignore",
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


platform_settings = PlatformSettings()
