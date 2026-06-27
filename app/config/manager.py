"""ConfigurationManager caching, accessing, and reloading configs."""

import datetime
import threading
import time
from typing import Any

from app.config.loader import ConfigurationLoader
from app.config.models import (
    ConfigurationReport,
    ConfigurationStatistics,
    RuntimeConfiguration,
)
from app.config.telemetry import ConfigurationTelemetry
from app.config.validator import ConfigurationValidator
from app.core.settings.config import settings


class ConfigurationManager:
    """Thread-safe centralized manager caching and exposing runtime configurations."""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *_args: Any, **_kwargs: Any) -> "ConfigurationManager":
        """Singleton pattern wrapper."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self) -> None:
        """Initialize the ConfigurationManager instance."""
        # Ensure initialization runs only once
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._config: RuntimeConfiguration | None = None
        self._report: ConfigurationReport | None = None
        self._loader = ConfigurationLoader()
        self._validator = ConfigurationValidator()

    def load_configuration(
        self,
        config_file_path: str | None = None,
        env_overrides: bool = True,
        profile_overrides: bool = True,
        programmatic_overrides: dict[str, Any] | None = None,
    ) -> RuntimeConfiguration:
        """Load, validate, cache, and apply configuration."""
        with self._lock:
            t_start = time.time()

            # Load raw merge
            raw_data, sources = self._loader.load(
                config_file_path=config_file_path,
                env_overrides=env_overrides,
                profile_overrides=profile_overrides,
                programmatic_overrides=programmatic_overrides,
            )

            # Validate configuration
            try:
                config, warnings = self._validator.validate(raw_data)
            except Exception as e:
                ConfigurationTelemetry.log_config_validation_failed(str(e))
                raise

            t_end = time.time()
            validation_time_ms = (t_end - t_start) * 1000.0

            # Build stats
            stats = ConfigurationStatistics(
                loaded_sources_count=len(sources),
                validation_time_ms=validation_time_ms,
                active_profile=config.app.app_env,
            )

            report = ConfigurationReport(
                loaded_at=datetime.datetime.now(datetime.UTC).isoformat(),
                statistics=stats,
                warnings=warnings,
                errors=[],
            )

            self._config = config
            self._report = report
            # Propagate to legacy global Settings object for backward compatibility
            self._apply_to_legacy_settings(config)

            ConfigurationTelemetry.log_config_loaded(
                profile=config.app.app_env,
                sources_count=len(sources),
                status="success",
            )

            return config

    def get_config(self) -> RuntimeConfiguration:
        """Retrieve the active cached configuration, loading default if not initialized."""
        with self._lock:
            if self._config is None:
                self.load_configuration()
            assert self._config is not None
            return self._config

    def get_report(self) -> ConfigurationReport:
        """Retrieve the configuration report for the active configuration."""
        with self._lock:
            if self._report is None:
                self.load_configuration()
            assert self._report is not None
            return self._report

    def reload(
        self,
        config_file_path: str | None = None,
        env_overrides: bool = True,
        profile_overrides: bool = True,
        programmatic_overrides: dict[str, Any] | None = None,
    ) -> RuntimeConfiguration:
        """Force a reload of the configuration from all specified sources."""
        return self.load_configuration(
            config_file_path=config_file_path,
            env_overrides=env_overrides,
            profile_overrides=profile_overrides,
            programmatic_overrides=programmatic_overrides,
        )

    def _apply_to_legacy_settings(self, config: RuntimeConfiguration) -> None:
        """Sync new config values back into the legacy global Settings object."""
        if hasattr(settings, "_update_snapshot"):
            settings._update_snapshot(config)
        else:
            new_values = {}
            for name in settings.model_fields:
                if name == "APP_VERSION":
                    continue
                if hasattr(config, name):
                    new_values[name] = getattr(config, name)
            settings.__dict__.update(new_values)
