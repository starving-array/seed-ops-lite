"""ConfigurationValidator validating configuration ranges and schemas."""

from typing import Any

from app.config.exceptions import ConfigurationValidationException
from app.config.models import RuntimeConfiguration


class ConfigurationValidator:
    """Validates configuration schema and logical ranges."""

    @staticmethod
    def validate(raw_data: dict[str, Any]) -> tuple[RuntimeConfiguration, list[str]]:
        """Validate configuration structure, types, and logic constraints.

        Returns:
            Tuple containing:
            - Validated RuntimeConfiguration instance
            - List of warning messages
        """
        warnings: list[str] = []

        # Pydantic schema validation
        try:
            config = RuntimeConfiguration(**raw_data)
        except Exception as e:
            raise ConfigurationValidationException(
                f"Configuration schema validation failed: {e}"
            ) from e

        # Logic constraints check
        # 1. Ports
        if not (1 <= config.app.app_port <= 65535):
            raise ConfigurationValidationException(
                f"Invalid app_port: {config.app.app_port}. Must be between 1 and 65535."
            )
        if not (1 <= config.redis.redis_port <= 65535):
            raise ConfigurationValidationException(
                f"Invalid redis_port: {config.redis.redis_port}. Must be between 1 and 65535."
            )

        # 2. Redis timeouts & connections
        if config.redis.redis_timeout_seconds <= 0:
            raise ConfigurationValidationException(
                f"Invalid redis_timeout_seconds: {config.redis.redis_timeout_seconds}. Must be positive."
            )
        if config.redis.redis_max_connections <= 0:
            raise ConfigurationValidationException(
                f"Invalid redis_max_connections: {config.redis.redis_max_connections}. Must be positive."
            )

        # 3. Workers
        if config.worker.concurrency <= 0:
            raise ConfigurationValidationException(
                f"Invalid worker concurrency: {config.worker.concurrency}. Must be positive."
            )
        if config.worker.max_workers <= 0:
            raise ConfigurationValidationException(
                f"Invalid worker max_workers: {config.worker.max_workers}. Must be positive."
            )

        # 4. LLM
        if config.llm.max_retries < 0:
            raise ConfigurationValidationException(
                f"Invalid llm max_retries: {config.llm.max_retries}. Must be non-negative."
            )
        if config.llm.timeout <= 0:
            raise ConfigurationValidationException(
                f"Invalid llm timeout: {config.llm.timeout}. Must be positive."
            )

        # 5. Seeder
        if config.seeder.max_records <= 0:
            raise ConfigurationValidationException(
                f"Invalid seeder max_records: {config.seeder.max_records}. Must be positive."
            )

        # Run security warnings checks that do not block loading
        if config.app.app_env == "production" and config.app.app_debug:
            warnings.append(
                "Security warning: Debug mode is enabled in production environment."
            )
        if config.app.app_env == "production" and not config.redis.redis_password:
            warnings.append(
                "Security warning: Redis password is empty in production environment."
            )

        return config, warnings
