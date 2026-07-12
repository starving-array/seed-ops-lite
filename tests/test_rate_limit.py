"""Tests for the RateLimitMiddleware."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware.middleware import RateLimitMiddleware


def test_rate_limit_allows_normal_traffic() -> None:
    app = FastAPI()

    @app.get("/test")
    async def test_route() -> dict:
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    client = TestClient(app)
    for _ in range(5):
        resp = client.get("/test")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


def test_rate_limit_blocks_excess_requests() -> None:
    app = FastAPI()

    @app.get("/llm/test")
    async def llm_route() -> dict:
        return {"ok": True}

    app.add_middleware(RateLimitMiddleware)

    client = TestClient(app, headers={"X-Forwarded-For": "10.0.0.1"})

    for _ in range(10):
        client.get("/llm/test")

    resp = client.get("/llm/test")
    assert resp.status_code == 429
    assert resp.json()["error"]["type"] == "RateLimitExceeded"


def test_health_bypasses_rate_limit() -> None:
    app = FastAPI()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "healthy"}

    app.add_middleware(RateLimitMiddleware)

    client = TestClient(app)
    for _ in range(100):
        resp = client.get("/health")
        assert resp.status_code == 200
