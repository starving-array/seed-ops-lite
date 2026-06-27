"""ConfigurationLoader implementation loading and merging configs."""

import copy
import json
import os
import types
from pathlib import Path
from typing import Any, Union, cast, get_args, get_origin

from app.config.exceptions import ConfigurationValidationException
from app.config.models import ConfigurationSource, RuntimeConfiguration
from app.config.profiles import RuntimeProfiles

ENV_MAPPING = {
    # App
    "SEEDOPS_APP_NAME": ("app", "app_name"),
    "SEEDOPS_APP_ENV": ("app", "app_env"),
    "SEEDOPS_APP_DEBUG": ("app", "app_debug"),
    "SEEDOPS_APP_HOST": ("app", "app_host"),
    "SEEDOPS_APP_PORT": ("app", "app_port"),
    # Redis
    "SEEDOPS_REDIS_HOST": ("redis", "redis_host"),
    "SEEDOPS_REDIS_PORT": ("redis", "redis_port"),
    "SEEDOPS_REDIS_DB": ("redis", "redis_db"),
    "SEEDOPS_REDIS_PASSWORD": ("redis", "redis_password"),
    "SEEDOPS_REDIS_TIMEOUT": ("redis", "redis_timeout_seconds"),
    "SEEDOPS_REDIS_MAX_CONNECTIONS": ("redis", "redis_max_connections"),
    # Logging
    "SEEDOPS_LOG_LEVEL": ("logging", "log_level"),
    "SEEDOPS_LOG_JSON": ("logging", "log_json_format"),
    # LLM
    "SEEDOPS_GEMINI_API_KEY": ("llm", "gemini_api_key"),
    "SEEDOPS_GEMINI_MODEL": ("llm", "gemini_model"),
    "SEEDOPS_LLM_RETRIES": ("llm", "max_retries"),
    "SEEDOPS_LLM_TIMEOUT": ("llm", "timeout"),
    # Workflow
    "SEEDOPS_WF_RETRIES": ("workflow", "max_retries"),
    "SEEDOPS_WF_TIMEOUT": ("workflow", "default_timeout"),
    # Worker
    "SEEDOPS_WORKER_CONCURRENCY": ("worker", "concurrency"),
    "SEEDOPS_WORKER_MAX_WORKERS": ("worker", "max_workers"),
    # Seeder
    "SEEDOPS_SEEDER_DEFAULT_SEED": ("seeder", "default_seed"),
    "SEEDOPS_SEEDER_MAX_RECORDS": ("seeder", "max_records"),
    # Binding
    "SEEDOPS_BINDING_STRICT": ("binding", "strict_mode"),
    "SEEDOPS_BINDING_MAX_DEPTH": ("binding", "max_depth"),
    # Export
    "SEEDOPS_EXPORT_FORMAT": ("export", "default_format"),
    "SEEDOPS_EXPORT_DIR": ("export", "target_directory"),
    # Observability
    "SEEDOPS_OBS_ENABLE": ("observability", "enable_telemetry"),
    "SEEDOPS_OBS_LOG_LEVEL": ("observability", "log_level"),
}


def parse_env_value(val: str, target_type: type) -> Any:
    """Convert env string to target python type."""
    if target_type is bool:
        return val.lower() in ("true", "1", "yes", "on")
    if target_type is int:
        return int(val)
    if target_type is float:
        return float(val)
    if val == "":
        return None
    return val


def resolve_field_type(sec: str, field: str) -> type[Any]:
    """Resolve target field type dynamically from RuntimeConfiguration schema."""
    sub_model_field = RuntimeConfiguration.model_fields.get(sec)
    if not sub_model_field or not sub_model_field.annotation:
        return str

    sub_model_cls = sub_model_field.annotation
    if hasattr(sub_model_cls, "model_fields"):
        field_info = sub_model_cls.model_fields.get(field)
        if field_info and field_info.annotation:
            ann = field_info.annotation
            origin = get_origin(ann)
            if origin is Union or (
                hasattr(types, "UnionType") and origin is types.UnionType
            ):
                args = get_args(ann)
                for arg in args:
                    if arg is not type(None):
                        return cast(type[Any], arg)
            return cast(type[Any], ann)
    return str


class ConfigurationLoader:
    """Loads and deterministically merges configuration from files, environment, and overrides."""

    @staticmethod
    def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge overrides dict into base dict."""
        merged = copy.deepcopy(base)
        for k, v in overrides.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k] = ConfigurationLoader.deep_merge(merged[k], v)
            else:
                merged[k] = copy.deepcopy(v)
        return merged

    def load(
        self,
        config_file_path: str | None = None,
        env_overrides: bool = True,
        profile_overrides: bool = True,
        programmatic_overrides: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[ConfigurationSource]]:
        """Load and merge configs deterministically, returning raw dictionary and loaded sources."""
        sources = []
        raw_config: dict[str, Any] = {}

        # 1. Base default configurations
        sources.append(ConfigurationSource(type="defaults", path="code_defaults"))

        # Resolve active profile name: programmatic > env > file > default ("development")
        active_profile = "development"
        if (
            programmatic_overrides
            and "app" in programmatic_overrides
            and "app_env" in programmatic_overrides["app"]
        ):
            active_profile = programmatic_overrides["app"]["app_env"]
        elif os.environ.get("SEEDOPS_APP_ENV"):
            active_profile = os.environ["SEEDOPS_APP_ENV"]
        elif config_file_path:
            config_path = Path(config_file_path)
            if config_path.exists():
                try:
                    with config_path.open(encoding="utf-8") as f:
                        file_data = json.load(f)
                        if "app" in file_data and "app_env" in file_data["app"]:
                            active_profile = file_data["app"]["app_env"]
                except Exception:  # noqa: S110
                    pass

        # 2. File source
        if config_file_path:
            config_path = Path(config_file_path)
            if config_path.exists():
                try:
                    with config_path.open(encoding="utf-8") as f:
                        file_data = json.load(f)
                except json.JSONDecodeError as e:
                    raise ConfigurationValidationException(
                        f"Malformed configuration file '{config_file_path}': {e}"
                    ) from e
                except Exception as e:
                    raise ConfigurationValidationException(
                        f"Failed to read configuration file '{config_file_path}': {e}"
                    ) from e

                raw_config = self.deep_merge(raw_config, file_data)
                sources.append(ConfigurationSource(type="file", path=config_file_path))

        # 3. Profile Overrides source
        if profile_overrides:
            overrides = RuntimeProfiles.get_overrides(active_profile)
            if overrides:
                raw_config = self.deep_merge(raw_config, overrides)
                sources.append(
                    ConfigurationSource(
                        type="profile", path=f"profiles.{active_profile}"
                    )
                )

        # 4. Environment Variables source
        if env_overrides:
            env_data: dict[str, Any] = {}
            has_env = False
            for env_key, val in os.environ.items():
                if env_key in ENV_MAPPING:
                    has_env = True
                    sec, field = ENV_MAPPING[env_key]
                    if sec not in env_data:
                        env_data[sec] = {}

                    # Target type inference dynamically from schema
                    target_type = resolve_field_type(sec, field)
                    try:
                        parsed_val = parse_env_value(val, target_type)
                    except Exception as e:
                        raise ConfigurationValidationException(
                            f"Failed to parse environment variable {env_key} value '{val}' to {target_type.__name__}: {e}"
                        ) from e
                    env_data[sec][field] = parsed_val
            if has_env:
                raw_config = self.deep_merge(raw_config, env_data)
                sources.append(ConfigurationSource(type="env", path="os.environ"))

        # 5. Programmatic Overrides source
        if programmatic_overrides:
            raw_config = self.deep_merge(raw_config, programmatic_overrides)
            sources.append(
                ConfigurationSource(type="overrides", path="programmatic_dictionary")
            )

        return raw_config, sources
