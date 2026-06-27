"""Redis connection manager providing async-first pooling and health checks."""

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.exceptions.exceptions import DatabaseConnectionError
from app.core.settings.config import settings


class RedisManager:
    """Manages async Redis connection pools and clients lifecycle."""

    def __init__(self) -> None:
        """Initialize the RedisManager with configuration parameters."""
        self._pool: aioredis.ConnectionPool | None = None  # type: ignore[type-arg]
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.db = settings.REDIS_DB
        self.password = settings.REDIS_PASSWORD
        self.timeout = settings.REDIS_TIMEOUT_SECONDS
        self.max_connections = settings.REDIS_MAX_CONNECTIONS

    async def connect(self) -> None:
        """Initialize the Redis connection pool.

        Raises:
            DatabaseConnectionError: If connection cannot be established
                or pool creation fails.
        """
        # Circular import protection
        from app.core.logging.logging import logger
        from app.telemetry.events import EventID

        if self._pool is not None:
            logger.warning(
                EventID.LOG_WARNING,
                "Redis connection pool already initialized.",
                component="RedisManager",
            )
            return

        try:
            logger.info(
                EventID.LOG_INFO,
                "Initializing Redis connection pool",
                component="RedisManager",
                host=self.host,
                port=self.port,
                db=self.db,
                max_connections=self.max_connections,
            )
            # Create connection pool
            self._pool = aioredis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                max_connections=self.max_connections,
                decode_responses=True,
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout,
            )
            # Test connection immediately
            async with self.get_client() as client:
                await client.ping()
            logger.info(
                EventID.REDIS_CONNECTED,
                "Successfully connected to Redis.",
                component="RedisManager",
            )
        except (RedisConnectionError, OSError) as exc:
            logger.error(
                EventID.LOG_ERROR,
                "Failed to connect to Redis",
                component="RedisManager",
                error=str(exc),
            )
            await self.disconnect()
            raise DatabaseConnectionError(
                f"Could not connect to Redis at {self.host}:{self.port}: {exc}"
            ) from exc

    async def disconnect(self) -> None:
        """Gracefully close the connection pool and release resources."""
        # Circular import protection
        from app.core.logging.logging import logger
        from app.telemetry.events import EventID

        if self._pool is not None:
            logger.info(
                EventID.REDIS_DISCONNECTED,
                "Closing Redis connection pool.",
                component="RedisManager",
            )
            await self._pool.disconnect()
            self._pool = None
            logger.info(
                EventID.REDIS_DISCONNECTED,
                "Redis connection pool closed.",
                component="RedisManager",
            )

    def get_client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Get an active Redis client from the pool.

        Returns:
            aioredis.Redis: Redis client instance.

        Raises:
            DatabaseConnectionError: If the pool has not been initialized.
        """
        if self._pool is None:
            raise DatabaseConnectionError("Redis connection pool is not initialized.")
        return aioredis.Redis(connection_pool=self._pool)

    async def check_health(self) -> bool:
        """Check if Redis connection is healthy.

        Returns:
            bool: True if connection is healthy, False otherwise.
        """
        # Circular import protection
        from app.core.logging.logging import logger
        from app.telemetry.events import EventID

        if self._pool is None:
            return False
        try:
            async with self.get_client() as client:
                response = await client.ping()
                return response is True
        except (RedisConnectionError, RedisTimeoutError, OSError) as exc:
            logger.error(
                EventID.LOG_ERROR,
                "Redis health check failed",
                component="RedisManager",
                error=str(exc),
            )
            return False


# Global Redis manager instance
redis_manager = RedisManager()
