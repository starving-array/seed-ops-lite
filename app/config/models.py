# ruff: noqa: N802
"""Configuration models defining all settings schemas."""

from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application parameters config."""

    app_name: str = Field(default="SeedOpsLite")
    app_env: Literal["development", "testing", "production"] = Field(
        default="development"
    )
    app_debug: bool = Field(default=True)
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)


class RedisConfig(BaseModel):
    """Redis cache and persistence parameters config."""

    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_db: int = Field(default=0)
    redis_password: str | None = Field(default=None)
    redis_timeout_seconds: int = Field(default=5)
    redis_max_connections: int = Field(default=10)


class LoggingConfig(BaseModel):
    """System logging format and level parameters config."""

    log_level: str = Field(default="info")
    log_json_format: bool = Field(default=True)


class WorkflowConfig(BaseModel):
    """Workflow Engine retry and timeout parameters config."""

    max_retries: int = Field(default=3)
    default_timeout: float = Field(default=60.0)


class WorkerConfig(BaseModel):
    """Worker Framework parallel concurrency parameters config."""

    concurrency: int = Field(default=4)
    max_workers: int = Field(default=8)


class SeederConfig(BaseModel):
    """Hybrid Seeder data generation parameters config."""

    default_seed: int | None = Field(default=None)
    max_records: int = Field(default=1000)


class BindingConfig(BaseModel):
    """Binding Engine integrity resolution parameters config."""

    strict_mode: bool = Field(default=True)
    max_depth: int = Field(default=5)


class ExportConfig(BaseModel):
    """Export Engine serialization targets parameters config."""

    default_format: str = Field(default="json")
    target_directory: str | None = Field(default=None)


class LLMConfig(BaseModel):
    """LLM Gateway request retry and latency parameters config."""

    provider: str = Field(default="google")
    model: str = Field(default="gemini-2.5-flash")
    max_retries: int = Field(default=3)
    timeout: float = Field(default=30.0)
    temperature: float = Field(default=0.2)
    max_output_tokens: int = Field(default=8192)


class ObservabilityConfig(BaseModel):
    """Execution telemetry and logging parameters config."""

    enable_telemetry: bool = Field(default=True)
    log_level: str = Field(default="info")


class RuntimeConfiguration(BaseModel):
    """Unified application runtime settings schema."""

    app: AppConfig = Field(default_factory=AppConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)
    seeder: SeederConfig = Field(default_factory=SeederConfig)
    binding: BindingConfig = Field(default_factory=BindingConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    # Legacy flat properties mapping for interface equivalence
    @property
    def APP_NAME(self) -> str:
        return self.app.app_name

    @property
    def APP_ENV(self) -> str:
        return self.app.app_env

    @property
    def APP_DEBUG(self) -> bool:
        return self.app.app_debug

    @property
    def APP_HOST(self) -> str:
        return self.app.app_host

    @property
    def APP_PORT(self) -> int:
        return self.app.app_port

    @property
    def REDIS_HOST(self) -> str:
        return self.redis.redis_host

    @property
    def REDIS_PORT(self) -> int:
        return self.redis.redis_port

    @property
    def REDIS_DB(self) -> int:
        return self.redis.redis_db

    @property
    def REDIS_PASSWORD(self) -> str | None:
        return self.redis.redis_password

    @property
    def REDIS_TIMEOUT_SECONDS(self) -> int:
        return self.redis.redis_timeout_seconds

    @property
    def REDIS_MAX_CONNECTIONS(self) -> int:
        return self.redis.redis_max_connections

    @property
    def LOG_LEVEL(self) -> str:
        return self.logging.log_level

    @property
    def LOG_JSON_FORMAT(self) -> bool:
        return self.logging.log_json_format

    @property
    def GEMINI_API_KEY(self) -> str | None:
        return None

    @property
    def GEMINI_MODEL(self) -> str:
        return self.llm.model

    @property
    def LLM_MAX_RETRIES(self) -> int:
        return self.llm.max_retries

    @property
    def LLM_TIMEOUT(self) -> float:
        return self.llm.timeout


class ConfigurationSource(BaseModel):
    """Represents a loading source target details."""

    type: Literal["defaults", "file", "env", "profile", "overrides"]
    path: str


class ConfigurationStatistics(BaseModel):
    """Statistical measurement of the configuration loading session."""

    loaded_sources_count: int
    validation_time_ms: float
    active_profile: str


class ConfigurationReport(BaseModel):
    """Unified report detailing loaded configurations."""

    loaded_at: str
    statistics: ConfigurationStatistics
    warnings: list[str]
    errors: list[str]
