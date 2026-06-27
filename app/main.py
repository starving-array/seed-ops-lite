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
        # Initialize storage & core dependencies
        await redis_manager.connect()
    except Exception as exc:  # pylint: disable=broad-except
        logger.critical(
            EventID.LOG_ERROR,
            "Failed to initialize critical application dependencies",
            error=str(exc),
        )

    yield

    # Shutdown actions
    logger.info(EventID.APP_STOPPED, "Shutting down SeedOps Lite application...")
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

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict this in production settings
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register custom correlation ID and error-logging middlewares
    # Note: Middlewares are executed in reverse order of addition.
    # CorrelationIdMiddleware runs first on incoming request.
    # ExceptionLoggingMiddleware runs second and has access to the
    # correlation ID context.
    app.add_middleware(ExceptionLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    # Include routers
    app.include_router(api_router)

    return app


app = create_app()
