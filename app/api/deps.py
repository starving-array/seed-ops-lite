from app.platform.container import (
    get_runtime_provider as get_runtime_provider_from_container,
)
from app.platform.runtime.interfaces import RuntimeProvider


async def get_runtime_provider() -> RuntimeProvider:
    """Dependency provider for retrieving the active RuntimeProvider (RuntimeManager).

    The RuntimeProvider manages transient runtime data only (queues, progress,
    cancellation flags, heartbeats, temporary caches). All durable data is
    stored exclusively in SQLite via SQLitePersistenceProvider.
    """
    return get_runtime_provider_from_container()
