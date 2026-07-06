"""Pytest configuration and global fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def override_test_platform_settings() -> None:
    """Override platform settings with test-friendly values to prevent .env contamination."""
    from app.core.settings.config import settings
    from app.platform.configuration.settings import platform_settings

    platform_settings.RUNTIME_CIRCUIT_BREAKER_FAILURE_THRESHOLD = 1
    platform_settings.RUNTIME_CIRCUIT_BREAKER_RECOVERY_SECONDS = 0.0
    platform_settings.RUNTIME_RECOVERY_POLL_INTERVAL_SECONDS = 0.05

    settings.GEMINI_API_KEY = "mock-key-for-testing"
    settings.GOOGLE_API_KEY = "mock-key-for-testing"


@pytest.fixture(autouse=True)
def reset_di_container() -> Generator[None, None, None]:
    """Isolate the global DI container for each test to prevent test contamination."""
    from app.core.lifecycle.container import container

    old_providers = dict(container._providers)
    old_instances = dict(container._instances)
    old_singletons = set(container._singletons)
    yield
    container._providers = old_providers
    container._instances = old_instances
    container._singletons = old_singletons


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session.

    Yields:
        asyncio.AbstractEventLoop: The asyncio event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Session-scoped fixture for creating the FastAPI app instance.

    Returns:
        FastAPI: The configured FastAPI application instance.
    """
    with (
        patch("app.core.lifecycle.redis.redis_manager.connect", new_callable=AsyncMock),
        patch(
            "app.core.lifecycle.redis.redis_manager.disconnect", new_callable=AsyncMock
        ),
    ):
        return create_app()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """Session-scoped fixture to redirect the database manager to a temporary SQLite file."""
    import contextlib
    import tempfile
    from pathlib import Path

    from app.platform.providers.sqlite_db import sqlite_db_manager

    fd, path = tempfile.mkstemp(suffix="_test.sqlite")
    import os

    os.close(fd)

    # Override the path and run migrations on the temp database
    sqlite_db_manager.db_path = path
    sqlite_db_manager.initialize(run_migrations=True)

    yield

    # Teardown database manager and remove temp file
    sqlite_db_manager.shutdown()
    p = Path(path)
    if p.exists():
        with contextlib.suppress(OSError):
            p.unlink()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Fixture for httpx AsyncClient to perform integration testing on FastAPI.

    Args:
        app: The FastAPI application fixture.

    Yields:
        AsyncClient: An asynchronous client bound to the FastAPI application.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as async_client:
        yield async_client
