"""Main entry point for the FastAPI SeedOps Lite application."""

# ruff: noqa: E402

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.config.manager import ConfigurationManager

# Atomically load configuration on application startup before other core modules initialize
ConfigurationManager().load_configuration()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.lifecycle.redis import redis_manager
from app.core.logging.logging import configure_logging, logger
from app.core.middleware.middleware import (
    CorrelationIdMiddleware,
    ExceptionLoggingMiddleware,
)
from app.core.settings.config import settings
from app.core.version import APP_VERSION
from app.telemetry.events import EventID


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages the startup and shutdown lifecycle of the FastAPI application."""
    # Startup actions
    configure_logging()
    logger.info(
        EventID.APP_STARTED,
        "Starting SeedOps Lite application...",
        version=APP_VERSION,
    )

    try:
        from app.core.storage.client import init_storage, is_local_memory_mode
        from app.platform.providers.sqlite_db import sqlite_db_manager

        # Initialize SQLite datastore and run migrations
        sqlite_db_manager.initialize()

        # Register platform provider bindings
        from app.platform.container import register_platform_providers
        from app.platform.providers.disk import (
            DiskArtifactProvider,
            DiskDatasetStorageManager,
        )
        from app.platform.providers.sqlite import SQLitePersistenceProvider
        from app.platform.runtime.manager import RuntimeManager

        sqlite_persistence_instance = SQLitePersistenceProvider()
        runtime_manager_instance = RuntimeManager()
        disk_artifact_instance = DiskArtifactProvider()
        disk_dataset_instance = DiskDatasetStorageManager()

        await runtime_manager_instance.initialize()

        register_platform_providers(
            persistence_factory=lambda: sqlite_persistence_instance,
            runtime_factory=lambda: runtime_manager_instance,
            artifact_factory=lambda: disk_artifact_instance,
            dataset_factory=lambda: disk_dataset_instance,
        )

        await init_storage()

        # Execute legacy datastore migration
        from app.platform.providers.migration import migrate_redis_to_sqlite

        await migrate_redis_to_sqlite()

        if is_local_memory_mode():
            logger.warning(
                EventID.LOG_WARNING,
                "Redis is currently unavailable. Live runtime features (queues, progress tracking and temporary caches) are operating in Local Runtime Mode. Persistent data—including projects, schemas, jobs and datasets—continues to be stored safely in SQLite.",
            )
    except Exception as exc:  # pylint: disable=broad-except
        logger.critical(
            EventID.LOG_ERROR,
            "Failed to initialize critical application dependencies",
            error=str(exc),
        )

    yield

    # Shutdown actions
    logger.info(EventID.APP_STOPPED, "Shutting down SeedOps Lite application...")
    import contextlib

    from app.core.storage.client import is_local_memory_mode
    from app.platform.container import get_runtime_provider
    from app.platform.providers.sqlite_db import sqlite_db_manager
    from app.platform.runtime.manager import RuntimeManager

    with contextlib.suppress(Exception):
        rm = get_runtime_provider()
        if isinstance(rm, RuntimeManager):
            await rm.close()

    sqlite_db_manager.shutdown()

    if not is_local_memory_mode():
        await redis_manager.disconnect()
    logger.info(EventID.APP_STOPPED, "Application shutdown complete.")


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance.

    Returns:
        FastAPI: The configured FastAPI application.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.APP_DEBUG,
        lifespan=lifespan,
    )

    # Register custom correlation ID and error-logging middlewares
    # Note: Middlewares are executed in reverse order of addition.
    # CorrelationIdMiddleware runs first on incoming request.
    # ExceptionLoggingMiddleware runs second and has access to the
    # correlation ID context.
    app.add_middleware(ExceptionLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # Configure CORS middleware last so it is executed outer-most on responses/exceptions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict this in production settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(api_router)

    return app


app = create_app()
