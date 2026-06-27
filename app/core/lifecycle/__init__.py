"""Lifecycle and operational state package."""

from app.core.lifecycle.container import DIContainer, container
from app.core.lifecycle.redis import RedisManager, redis_manager
from app.core.lifecycle.state import (
    get_python_version,
    get_startup_time_iso,
    get_uptime,
)

__all__ = [
    "DIContainer",
    "container",
    "RedisManager",
    "redis_manager",
    "get_python_version",
    "get_startup_time_iso",
    "get_uptime",
]
