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


@router.get("/analytics")
async def get_llm_analytics() -> dict[str, Any]:
    """Return aggregated LLM token usage, cost, latency, and error analytics.

    Covers today, last 7 days, last 30 days, and per-provider breakdown.
    All data sourced from the persistent llm_telemetry table.
    """
    import contextlib
    import datetime

    from sqlalchemy import text

    from app.platform.providers.sqlite_db import sqlite_db_manager

    def empty_window() -> dict[str, Any]:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost": 0.0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_latency_ms": 0.0,
            "avg_cost": 0.0,
        }

    def _query_window(s: Any, since_iso: str) -> dict[str, Any]:
        row = s.execute(
            text(
                "SELECT "
                "  COALESCE(SUM(prompt_tokens), 0), "
                "  COALESCE(SUM(completion_tokens), 0), "
                "  COALESCE(SUM(total_tokens), 0), "
                "  COALESCE(SUM(estimated_cost), 0.0), "
                "  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), "
                "  SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END), "
                "  AVG(CASE WHEN status = 'success' THEN latency_ms END), "
                "  AVG(CASE WHEN status = 'success' THEN estimated_cost END) "
                "FROM llm_telemetry WHERE timestamp >= :since"
            ),
            {"since": since_iso},
        ).one()
        return {
            "prompt_tokens": int(row[0] or 0),
            "completion_tokens": int(row[1] or 0),
            "total_tokens": int(row[2] or 0),
            "estimated_cost": round(float(row[3] or 0.0), 6),
            "successful_requests": int(row[4] or 0),
            "failed_requests": int(row[5] or 0),
            "avg_latency_ms": round(float(row[6] or 0.0), 2),
            "avg_cost": round(float(row[7] or 0.0), 8),
        }

    now = datetime.datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    week_start = (now - datetime.timedelta(days=7)).isoformat()
    month_start = (now - datetime.timedelta(days=30)).isoformat()

    today_stats = empty_window()
    week_stats = empty_window()
    month_stats = empty_window()
    provider_breakdown: dict[str, Any] = {}

    try:
        with sqlite_db_manager.session() as s:
            today_stats = _query_window(s, today_start)
            week_stats = _query_window(s, week_start)
            month_stats = _query_window(s, month_start)

            # Per-provider breakdown (all time)
            rows = s.execute(
                text(
                    "SELECT provider, "
                    "  COALESCE(SUM(total_tokens), 0), "
                    "  COALESCE(SUM(estimated_cost), 0.0), "
                    "  AVG(latency_ms), "
                    "  SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END), "
                    "  SUM(CASE WHEN retry_count > 0 THEN retry_count ELSE 0 END), "
                    "  COUNT(*) "
                    "FROM llm_telemetry "
                    "GROUP BY provider"
                )
            ).all()
            for r in rows:
                provider_breakdown[r[0]] = {
                    "total_tokens": int(r[1] or 0),
                    "estimated_cost": round(float(r[2] or 0.0), 6),
                    "avg_latency_ms": round(float(r[3] or 0.0), 2),
                    "failures": int(r[4] or 0),
                    "retries": int(r[5] or 0),
                    "total_requests": int(r[6] or 0),
                }
    except Exception:  # noqa: S110
        pass

    # Active provider/model from config
    active_provider = "unknown"
    active_model = "unknown"
    with contextlib.suppress(Exception):
        cfg = resolve_llm_config()
        active_provider = cfg.get("provider") or "unknown"
        active_model = cfg.get("model") or "unknown"

    return {
        "active_provider": active_provider,
        "active_model": active_model,
        "today": today_stats,
        "last_7_days": week_stats,
        "last_30_days": month_stats,
        "provider_breakdown": provider_breakdown,
    }
