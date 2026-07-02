from app.core.lifecycle.redis import redis_manager
from app.core.storage.base import BaseStorage, MemoryStorage, RedisStorage

_storage: BaseStorage | None = None
_is_local_memory_mode = False


async def init_storage() -> None:
    """Initialize active storage client.

    Attempts to connect to Redis; falls back to MemoryStorage if Redis connection fails.
    """
    global _storage, _is_local_memory_mode  # noqa: PLW0603
    try:
        await redis_manager.connect()
        client = redis_manager.get_client()
        _storage = RedisStorage(client)
        _is_local_memory_mode = False
    except Exception:
        # Fall back to memory storage on connection errors
        _storage = MemoryStorage()
        _is_local_memory_mode = True


def get_storage() -> BaseStorage:
    """Get the active storage implementation instance.

    Returns:
        BaseStorage: The current storage manager instance.
    """
    global _storage  # noqa: PLW0603
    if _storage is None:
        _storage = MemoryStorage()
    return _storage


def is_local_memory_mode() -> bool:
    """Check if the application is running in local in-memory storage mode.

    Returns:
        bool: True if MemoryStorage is active, False otherwise.
    """
    return _is_local_memory_mode
