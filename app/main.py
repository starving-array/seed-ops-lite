"""Main entry point for the FastAPI SeedOps Lite application."""

# ruff: noqa: E402

import datetime

# Python 3.10 compatibility: datetime.UTC was added in 3.11
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc  # noqa: UP017 — needed for Python 3.10

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.config.manager import ConfigurationManager

# Atomically load configuration on application startup before other core modules initialize
ConfigurationManager().load_configuration()

from app.core.logging.logging import configure_logging

configure_logging()

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.router import api_router
from app.core.lifecycle.redis import redis_manager
from app.core.logging.logging import logger
from app.core.middleware.middleware import (
    CorrelationIdMiddleware,
    ExceptionLoggingMiddleware,
    ProjectMiddleware,
    RateLimitMiddleware,
)
from app.core.settings.config import settings
from app.core.version import APP_VERSION
from app.telemetry.events import EventID


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages the startup and shutdown lifecycle of the FastAPI application."""
    import time

    startup_start = time.perf_counter()

    sqlite_status = "Unknown"

    try:
        from app.core.storage.client import init_storage, is_local_memory_mode
        from app.platform.providers.sqlite_db import sqlite_db_manager

        # Initialize SQLite datastore and run migrations
        sqlite_db_manager.initialize()
        sqlite_status = "Healthy"

        # Register platform provider bindings
        from app.platform.container import register_platform_providers
        from app.platform.providers.disk import (
            DiskArtifactProvider,
            DiskDatasetStorageManager,
        )
        from app.platform.providers.sqlite import SQLitePersistenceProvider
        from app.platform.runtime.manager import runtime_manager

        sqlite_persistence_instance = SQLitePersistenceProvider()
        disk_artifact_instance = DiskArtifactProvider()
        disk_dataset_instance = DiskDatasetStorageManager()

        await runtime_manager.initialize()

        register_platform_providers(
            persistence_factory=lambda: sqlite_persistence_instance,
            runtime_factory=lambda: runtime_manager,
            artifact_factory=lambda: disk_artifact_instance,
            dataset_factory=lambda: disk_dataset_instance,
        )

        await init_storage()

        # Execute legacy datastore migration
        from app.platform.providers.migration import migrate_redis_to_sqlite

        await migrate_redis_to_sqlite()

        redis_status = "Local Memory Mode" if is_local_memory_mode() else "Healthy"
    except Exception as exc:  # pylint: disable=broad-except
        sqlite_status = "Unhealthy"
        logger.critical(
            EventID.LOG_ERROR,
            "Failed to initialize critical application dependencies",
            error=str(exc),
        )

    startup_dur = (time.perf_counter() - startup_start) * 1000.0

    # Print clean startup summary block
    logger.info(
        EventID.APP_STARTED,
        "SeedOps Application Startup Summary",
        application_version=APP_VERSION,
        environment=settings.APP_ENV,
        sqlite_status=sqlite_status,
        redis_status=redis_status,
        runtime_provider=(
            "RedisRuntimeProvider"
            if redis_status == "Healthy"
            else "LocalMemoryProvider"
        ),
        persistence_provider="SQLitePersistenceProvider",
        artifact_provider="DiskArtifactProvider",
        dataset_provider="DiskDatasetStorageManager",
        registered_services=",".join(
            [
                "SQLitePersistenceProvider",
                "RuntimeManager",
                "DiskArtifactProvider",
                "DiskDatasetStorageManager",
            ]
        ),
        startup_duration=f"{startup_dur:.2f} ms",
    )

    yield

    # Shutdown actions
    shutdown_start = time.perf_counter()
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

    shutdown_dur = (time.perf_counter() - shutdown_start) * 1000.0
    logger.info(
        EventID.APP_STOPPED,
        "Application Shutdown Summary",
        shutdown_status="Success",
        shutdown_duration=f"{shutdown_dur:.2f} ms",
    )


def create_api_app() -> FastAPI:
    """Creates the FastAPI application with API routes only.

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
    app.add_middleware(ProjectMiddleware)

    # Configure CORS middleware last so it is executed outer-most on responses/exceptions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict this in production settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting — applied to all API routes
    app.add_middleware(RateLimitMiddleware)

    # Include routers
    app.include_router(api_router)

    return app


def create_app() -> FastAPI:
    """Creates the FastAPI application with landing page and frontend serving.

    Returns:
        FastAPI: The configured FastAPI application.
    """
    app = create_api_app()

    project_root = Path(__file__).resolve().parent.parent
    frontend_public = project_root / "frontend" / "public"
    frontend_dist = project_root / "frontend" / "dist"

    # Serve landing page at /
    @app.get("/", response_class=FileResponse)
    async def landing() -> FileResponse:
        landing_file = frontend_public / "index-landing.html"
        if landing_file.exists():
            return FileResponse(str(landing_file))
        return FileResponse(str(frontend_dist / "index-landing.html"))

    # Serve React SPA at /app (catch-all for client-side routing)
    @app.get("/app", response_class=FileResponse)
    @app.get("/app/{rest:path}", response_class=FileResponse)
    async def serve_frontend(rest: str = "") -> FileResponse:
        file_path = frontend_dist / rest
        if rest and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"))

    return app


app = create_app()
