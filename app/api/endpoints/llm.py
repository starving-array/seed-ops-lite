"""API endpoints for LLM provider configuration, registry mapping, and manual health checks."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.settings.config import settings
from app.llm.config_resolver import resolve_llm_config
from app.llm.provider import provider_registry

router = APIRouter()


class LLMConfigPayload(BaseModel):
    provider: str
    model: str
    auto_failover: bool
    fallback_order: str


@router.get("/providers")
async def list_providers() -> list[dict[str, Any]]:
    """List all registered providers and their details."""
    providers = []
    for p in provider_registry.listProviders():
        providers.append(
            {
                "name": p.name(),
                "is_available": p.is_available(),
                "auth_status": p.auth_status(),
                "supported_models": p.supported_models(),
                "capabilities": p.capabilities(),
            }
        )
    return providers


@router.get("/config")
async def get_llm_config() -> dict[str, Any]:
    """Retrieve current active resolved LLM configuration details."""
    return resolve_llm_config()


@router.post("/config")
async def save_llm_config(payload: LLMConfigPayload) -> dict[str, str]:
    """Save/update LLM settings directly to SQLite app_settings database namespace."""
    from sqlalchemy import text

    from app.platform.providers.sqlite_db import sqlite_db_manager

    try:
        # SQLite db session
        with sqlite_db_manager.session() as s:
            # Helper to upsert a setting
            def upsert_setting(key: str, val: str) -> None:
                exists = (
                    s.execute(
                        text("SELECT count(*) FROM app_settings WHERE key = :key"),
                        {"key": key},
                    ).scalar()
                    or 0
                )
                if exists > 0:
                    s.execute(
                        text("UPDATE app_settings SET value = :val WHERE key = :key"),
                        {"key": key, "val": val},
                    )
                else:
                    s.execute(
                        text(
                            "INSERT INTO app_settings (key, value) VALUES (:key, :val)"
                        ),
                        {"key": key, "val": val},
                    )

            upsert_setting("ai_active_provider", payload.provider)
            upsert_setting("ai_active_model", payload.model)
            upsert_setting(
                "ai_auto_failover", "true" if payload.auto_failover else "false"
            )
            upsert_setting("ai_fallback_order", payload.fallback_order)

            # Sync active settings singleton in memory
            settings.LLM_PROVIDER = payload.provider
            settings.LLM_MODEL = payload.model
            settings.LLM_AUTO_FAILOVER = payload.auto_failover
            settings.LLM_FALLBACK_ORDER = payload.fallback_order

            s.commit()
        return {
            "status": "success",
            "message": "LLM configurations saved successfully.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save settings: {exc}",
        ) from exc


@router.post("/healthcheck")
async def run_health_check() -> dict[str, Any]:
    """Execute manual lightweight verification request on all configured providers."""
    results = {}
    for p in provider_registry.listProviders():
        p_name = p.name()
        # Prevent checking duplicate aliases in list
        if p_name in results:
            continue
        try:
            res = await p.healthCheck()
            results[p_name] = res
        except Exception as exc:
            results[p_name] = {
                "status": "Unavailable",
                "error": str(exc),
                "latency_ms": 0,
            }
    return results
