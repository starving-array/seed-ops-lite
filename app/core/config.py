"""Proxy for core/config.py backward compatibility."""

from app.core.settings.config import Settings, settings

__all__ = ["Settings", "settings"]
