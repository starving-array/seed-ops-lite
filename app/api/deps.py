"""Dependency injection providers for FastAPI endpoints."""

from app.core.storage.base import BaseStorage
from app.core.storage.client import get_storage


async def get_redis() -> BaseStorage:
    """Dependency provider for retrieving the active storage backend (Redis or Memory)."""
    return get_storage()
