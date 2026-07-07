import contextlib
from typing import Any

from sqlalchemy import text

from app.core.settings.config import settings
from app.llm.exceptions import LLMConfigurationError


def get_app_setting_sync(key: str) -> str | None:
    """Retrieve app setting from SQLite database synchronously, ignoring errors."""
    try:
        from app.platform.providers.sqlite_db import sqlite_db_manager

        if not sqlite_db_manager._engine:
            sqlite_db_manager.initialize(run_migrations=False)
        with sqlite_db_manager.session() as s:
            val = s.execute(
                text("SELECT value FROM app_settings WHERE key = :key"), {"key": key}
            ).scalar()
            return str(val) if val is not None else None
    except Exception:
        return None


def resolve_llm_config() -> dict[str, Any]:
    """Resolves the LLM configuration based on precedence:
    1. Advanced Settings in DB
    2. Environment variables (.env)
    3. Built-in defaults
    """
    # 1. Advanced settings from DB
    db_provider = get_app_setting_sync("ai_active_provider")
    db_model = get_app_setting_sync("ai_active_model")
    db_temp = get_app_setting_sync("ai_temperature")
    db_tokens = get_app_setting_sync("ai_max_output_tokens")
    db_failover = get_app_setting_sync("ai_auto_failover")
    db_fallback_order = get_app_setting_sync("ai_fallback_order")

    # 2. Environment variables & fallback defaults
    # LLM Provider
    provider = db_provider or getattr(settings, "LLM_PROVIDER", None) or "google"
    provider = provider.strip().lower()
    if provider == "gemini":
        provider = "google"

    # Model
    model = None
    model = db_model.strip() if db_model else getattr(settings, "LLM_MODEL", None)

    # Built-in defaults fallback per provider
    if not model:
        if provider in ("google", "gemini", "vertex"):
            model = "gemini-2.5-flash"
        elif provider in ("openai", "azure"):
            model = "gpt-4o"
        elif provider == "anthropic":
            model = "claude-3-5-sonnet"
        elif provider == "ollama":
            model = "llama3"
        else:
            model = "gemini-2.5-flash"

    # Temperature
    temperature = 0.2
    if db_temp:
        with contextlib.suppress(ValueError):
            temperature = float(db_temp)
    else:
        temperature = getattr(settings, "LLM_TEMPERATURE", 0.2)

    # Max Output Tokens
    max_tokens = 8192
    if db_tokens:
        with contextlib.suppress(ValueError):
            max_tokens = int(db_tokens)
    else:
        max_tokens = getattr(settings, "LLM_MAX_OUTPUT_TOKENS", 8192)

    timeout = getattr(settings, "LLM_TIMEOUT", 30.0)
    max_retries = getattr(settings, "LLM_MAX_RETRIES", 3)

    # Auto Failover & Fallback Order
    auto_failover = True
    if db_failover is not None:
        auto_failover = db_failover.lower() == "true"
    else:
        env_failover = getattr(settings, "LLM_AUTO_FAILOVER", "true")
        if isinstance(env_failover, bool):
            auto_failover = env_failover
        else:
            auto_failover = str(env_failover).lower() == "true"

    fallback_order_list = ["vertex", "gemini", "anthropic", "openai", "ollama"]
    fallback_order_str = db_fallback_order or getattr(
        settings, "LLM_FALLBACK_ORDER", None
    )
    if fallback_order_str:
        if isinstance(fallback_order_str, list):
            fallback_order_list = fallback_order_str
        else:
            fallback_order_list = [
                x.strip().lower()
                for x in str(fallback_order_str).split(",")
                if x.strip()
            ]

    # Resolve active API Key based on provider
    api_key = None
    enabled = True

    if provider in ("google", "gemini"):
        api_key = getattr(settings, "GOOGLE_API_KEY", None) or getattr(
            settings, "GEMINI_API_KEY", None
        )
    elif provider == "vertex":
        # Vertex does not use API key, it uses ADC
        api_key = None
    elif provider == "openai":
        api_key = getattr(settings, "OPENAI_API_KEY", None)
    elif provider == "anthropic":
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    elif provider == "azure":
        api_key = getattr(settings, "AZURE_OPENAI_API_KEY", None)
    elif provider == "ollama":
        api_key = "local"

    return {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "max_output_tokens": max_tokens,
        "timeout": timeout,
        "max_retries": max_retries,
        "api_key": api_key,
        "google_cloud_project": getattr(settings, "GOOGLE_CLOUD_PROJECT", None),
        "google_cloud_location": getattr(settings, "GOOGLE_CLOUD_LOCATION", None),
        "enabled": enabled,
        "auto_failover": auto_failover,
        "fallback_order": fallback_order_list,
    }


def validate_llm_config(config: dict[str, Any]) -> None:
    """Validate LLM config parameters using provider registry."""
    provider = str(config.get("provider") or "google").strip().lower()
    if provider == "gemini":
        provider = "google"
    from app.llm.provider import provider_registry

    try:
        provider_registry.getProvider(provider)
    except Exception as exc:
        raise LLMConfigurationError(f"Unsupported LLM provider: {provider}") from exc

    # Bypass api key validation in testing environments
    import sys

    is_testing = (
        getattr(settings, "APP_ENV", "development") == "testing"
        or "pytest" in sys.modules
    ) and not config.get("force_validation")
    if not is_testing:
        valid = True
        if provider == "openai":
            key = config.get("api_key") or getattr(settings, "OPENAI_API_KEY", None)
            if not key:
                valid = False
        elif provider == "anthropic":
            key = config.get("api_key") or getattr(settings, "ANTHROPIC_API_KEY", None)
            if not key:
                valid = False
        elif provider in ("google", "gemini"):
            key = (
                config.get("api_key")
                or getattr(settings, "GOOGLE_API_KEY", None)
                or getattr(settings, "GEMINI_API_KEY", None)
            )
            if not key:
                valid = False
        elif provider == "azure":
            key = config.get("api_key") or getattr(
                settings, "AZURE_OPENAI_API_KEY", None
            )
            endpoint = config.get("azure_endpoint") or getattr(
                settings, "AZURE_OPENAI_ENDPOINT", None
            )
            if not key or not endpoint:
                valid = False
        elif provider == "vertex":
            proj = config.get("google_cloud_project") or getattr(
                settings, "GOOGLE_CLOUD_PROJECT", None
            )
            loc = config.get("google_cloud_location") or getattr(
                settings, "GOOGLE_CLOUD_LOCATION", None
            )
            if not proj or not loc:
                valid = False
        elif provider == "ollama":
            pass
        elif not config.get("api_key"):
            valid = False

        if not valid:
            raise LLMConfigurationError(
                f"Credentials/keys not configured for provider: {provider}"
            )

    if not config.get("model"):
        raise LLMConfigurationError(
            f"LLM model is not configured for provider: {provider}"
        )
