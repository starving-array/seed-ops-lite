"""Configuration module for the SeedOps Lite application using Pydantic Settings."""

from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.version import APP_VERSION


class Settings(BaseSettings):
    """Application settings class.

    Loads values from environment variables and uses defaults if not present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application Configurations
    APP_NAME: str = Field(default="SeedOpsLite")
    APP_ENV: Literal["development", "production", "staging", "testing"] = Field(
        default="development"
    )
    APP_DEBUG: bool = Field(default=True)
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000)
    APP_VERSION: str = Field(default=APP_VERSION)

    # Redis Configurations
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    REDIS_PASSWORD: str | None = Field(default=None)
    REDIS_TIMEOUT_SECONDS: int = Field(default=5)
    REDIS_MAX_CONNECTIONS: int = Field(default=10)

    # Logging Configurations
    LOG_LEVEL: str = Field(default="info")
    LOG_JSON_FORMAT: bool = Field(default=True)
    # When True, force the pretty dev console formatter regardless of APP_ENV.
    # When False (default), the formatter is chosen automatically: pretty in
    # development, structured JSON in staging/production.
    LOG_PRETTY: bool = Field(default=False)
    # Operations exceeding this threshold (ms) are flagged as slow in the logs.
    SLOW_LOG_THRESHOLD_MS: float = Field(default=500.0)

    # LLM Gateway Configurations
    LLM_PROVIDER: str = Field(default="google")
    LLM_MODEL: str = Field(default="gemini-2.5-flash")
    LLM_AUTO_FAILOVER: bool = Field(default=True)
    LLM_FALLBACK_ORDER: str = Field(default="vertex,gemini,anthropic,openai,ollama")
    LLM_MAX_RETRIES: int = Field(default=3)
    LLM_TIMEOUT: float = Field(default=30.0)
    LLM_TEMPERATURE: float = Field(default=0.2)
    LLM_MAX_OUTPUT_TOKENS: int = Field(default=8192)

    # Google Provider
    GOOGLE_ENABLED: bool = Field(default=True)
    GOOGLE_API_KEY: str | None = Field(default=None)
    GOOGLE_MODEL: str = Field(default="gemini-2.5-flash")
    GOOGLE_CLOUD_PROJECT: str | None = Field(default=None)
    GOOGLE_CLOUD_LOCATION: str | None = Field(default=None)

    # OpenAI Provider
    OPENAI_ENABLED: bool = Field(default=False)
    OPENAI_API_KEY: str | None = Field(default=None)
    OPENAI_MODEL: str | None = Field(default=None)

    # Anthropic Provider
    ANTHROPIC_ENABLED: bool = Field(default=False)
    ANTHROPIC_API_KEY: str | None = Field(default=None)
    ANTHROPIC_MODEL: str | None = Field(default=None)

    # Legacy Aliases (backward compatibility)
    GEMINI_API_KEY: str | None = Field(default=None)
    GEMINI_MODEL: str = Field(default="gemini-2.5-flash")

    # Email Branding Configurations
    DEFAULT_EMAIL_DOMAIN: str = Field(default="seedops.com")

    # Batch Size Threshold Configurations
    BATCH_THRESHOLD_SMALL: int = Field(default=100)
    BATCH_THRESHOLD_MEDIUM: int = Field(default=1000)
    BATCH_THRESHOLD_LARGE: int = Field(default=10000)

    BATCH_SIZE_SMALL: int = Field(default=10)
    BATCH_SIZE_MEDIUM: int = Field(default=50)
    BATCH_SIZE_LARGE: int = Field(default=250)
    BATCH_SIZE_XLARGE: int = Field(default=500)

    def _update_snapshot(self, config: Any) -> None:
        """Atomically update legacy settings using a single dict update under the GIL."""
        new_values = {}
        for name in self.model_fields:
            if name == "APP_VERSION":
                continue
            if hasattr(config, name):
                new_values[name] = getattr(config, name)

        # GIL-thread-safe dictionary update for atomic property substitution
        self.__dict__.update(new_values)


# Global settings instance
settings = Settings()
