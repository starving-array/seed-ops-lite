"""Pytest configuration and global fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_app


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
