"""Runtime profiles definitions overriding base configurations."""

from typing import Any, ClassVar


class RuntimeProfiles:
    """Provides deterministic overrides for development, testing, and production profiles."""

    _PROFILES: ClassVar[dict[str, dict[str, Any]]] = {
        "development": {
            "app": {
                "app_env": "development",
                "app_debug": True,
            },
            "logging": {
                "log_level": "debug",
                "log_json_format": False,
            },
        },
        "testing": {
            "app": {
                "app_env": "testing",
                "app_debug": True,
            },
            "logging": {
                "log_level": "warning",
                "log_json_format": False,
            },
            "redis": {
                "redis_db": 9,
            },
            "seeder": {
                "default_seed": 42,
            },
            "worker": {
                "max_workers": 1,
            },
        },
        "production": {
            "app": {
                "app_env": "production",
                "app_debug": False,
            },
            "logging": {
                "log_level": "info",
                "log_json_format": True,
            },
        },
    }

    @classmethod
    def get_overrides(cls, profile_name: str) -> dict[str, Any]:
        """Return configuration overrides for the specified profile."""
        profile = profile_name.lower().strip()
        return cls._PROFILES.get(profile, {})
