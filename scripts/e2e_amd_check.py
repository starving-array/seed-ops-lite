#!/usr/bin/env python3
"""E2E validation script for the AMD ROCm + Fireworks stack.

Run this on the AMD GPU instance to verify everything works end-to-end.

Usage:
    uv run python scripts/e2e_amd_check.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

sys.stdout.reconfigure(encoding='utf-8')  # noqa: ERA001

import httpx

from app.llm.gateway import _resolve_routing_order
from app.llm.model_manager import get_model_info, list_catalogue, list_local_models
from app.llm.provider import _format_gemma_prompt, provider_registry
from app.core.settings.config import settings


PASS = 0
FAIL = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  [OK] {msg}")


def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def check(cond: bool, msg: str) -> None:
    if cond:
        ok(msg)
    else:
        fail(msg)


# ── 1. ROCm Provider ──────────────────────────────────────────────────

def check_rocm_provider() -> None:
    print("\n  ── 1. ROCm Provider ──")
    try:
        p = provider_registry.getProvider("rocm")
        check(p.name() == "ROCm", "Provider name is 'ROCm'")
        check(p.is_available(), "ROCm is_available()")
        check("AMD" in p.auth_status(), f"Auth status: {p.auth_status()}")
        models = p.supported_models()
        check(len(models) > 0, f"Supports {len(models)} models")
        check(any("gemma" in m for m in models), "Includes Gemma models")
        check(p.estimateCost("gemma-2-9b-it", 100, 50) == 0.0, "Cost is zero")
        caps = p.capabilities()
        check(caps["json_mode"], "JSON mode supported")
    except Exception as e:
        fail(f"ROCm provider error: {e}")


# ── 2. Fireworks Provider ─────────────────────────────────────────────

def check_fireworks_provider() -> None:
    print("\n  ── 2. Fireworks Provider ──")
    try:
        p = provider_registry.getProvider("fireworks")
        check(p.name() == "Fireworks AI", "Provider name is 'Fireworks AI'")
        available = p.is_available()
        check(available, f"is_available() = {available}")
        if available:
            check("Key" in p.auth_status(), f"Auth: {p.auth_status()}")
        models = p.supported_models()
        check(any("gemma" in m for m in models), "Includes Gemma models")
        caps = p.capabilities()
        check(caps["json_mode"], "JSON mode supported")
        check(caps["tool_calling"], "Tool calling supported")
    except Exception as e:
        fail(f"Fireworks provider error: {e}")


# ── 3. Model Manager ──────────────────────────────────────────────────

def check_model_manager() -> None:
    print("\n  ── 3. Model Catalogue ──")
    catalogue = list_catalogue()
    check(len(catalogue) >= 3, f"{len(catalogue)} models in catalogue")
    info = get_model_info("gemma-2-9b-it")
    check(info is not None, "gemma-2-9b-it found in catalogue")
    if info:
        check("huggingface.co" in info.hf_repo or "hf" in info.hf_repo, "Has HF source")

    models_dir = getattr(settings, "ROCm_MODELS_DIR", "./models/rocm")
    local = list_local_models(models_dir)
    downloaded = [m for m in local if m["downloaded"]]
    if downloaded:
        ok(f"{len(downloaded)} model(s) already downloaded")
        for m in downloaded:
            print(f"         {m['name']} ({m['size_mb']} MB)")
    else:
        print("  [INFO] No models downloaded yet. Run: python scripts/download_model.py download gemma-2-9b-it")


# ── 4. Gemma Prompt Format ────────────────────────────────────────────

def check_gemma_prompt() -> None:
    print("\n  ── 4. Gemma Prompt Format ──")
    result = _format_gemma_prompt("test")
    check("<start_of_turn>user" in result, "Has user turn marker")
    check("<end_of_turn>" in result, "Has end turn marker")
    check("<start_of_turn>model" in result, "Has model turn marker")
    json_result = _format_gemma_prompt("test", json_mode=True)
    check("JSON" in json_result, "JSON mode adds JSON instruction")


# ── 5. Routing ────────────────────────────────────────────────────────

def check_routing() -> None:
    print("\n  ── 5. Model Routing ──")
    fallback = ["vertex", "gemini", "anthropic", "openai", "fireworks", "rocm", "ollama"]
    gemma_order = _resolve_routing_order("gemma-2-9b-it", fallback)
    check(gemma_order.index("rocm") < gemma_order.index("vertex"), "Gemma: ROCm before Vertex")
    check(gemma_order.index("fireworks") < gemma_order.index("vertex"), "Gemma: Fireworks before Vertex")
    other_order = _resolve_routing_order("gpt-4o", fallback)
    check(other_order == fallback, "Non-Gemma models use default order")


# ── 6. Live Generation Test ───────────────────────────────────────────

async def check_live_generation() -> None:
    try:
        from app.core.config import settings
        provider = settings.LLM_PROVIDER or "fireworks"
        model = settings.LLM_MODEL or ""
        print(f"\n  ── 6. Live Generation (via {provider}) ──")
        from app.llm.gateway import LLMGateway
        from app.llm.models import LLMRequest

        gateway = LLMGateway()
        start = time.perf_counter()
        resp = await gateway.generate(
            LLMRequest(prompt="Say hello in one word", max_tokens=10, temperature=0.1, provider=provider, model=model)
        )
        elapsed = time.perf_counter() - start
        check(len(resp.text) > 0, f"Generated response ({elapsed:.1f}s): {resp.text.strip()}")
        check(resp.usage.total_tokens is not None, "Token usage reported")
        check(resp.usage.latency_ms is not None, "Latency measured")
    except Exception as e:
        fail(f"Live generation error: {e}")


# ── 7. Docker build check (optional) ──────────────────────────────────

def check_dockerfile() -> None:
    print("\n  ── 7. Docker ──")
    dockerfile = Path("docker/Dockerfile")
    check(dockerfile.exists(), "CPU Dockerfile exists")
    rocm_df = Path("docker/Dockerfile.rocm")
    check(rocm_df.exists(), "ROCm Dockerfile exists")
    compose = Path("docker-compose.yml")
    check(compose.exists(), "docker-compose.yml exists")


# ── 8. Demo wizard ────────────────────────────────────────────────────

def check_demo_wizard() -> None:
    print("\n  ── 8. Demo Wizard ──")
    wizard = Path("scripts/demo_wizard.py")
    check(wizard.exists(), "demo_wizard.py exists")


# ── Main ──────────────────────────────────────────────────────────────

async def main() -> None:
    print()
    print("  +-----------------------------------------------+")
    print("  |   SafeSeedOps Lite -- AMD Stack E2E Check     |")
    print("  +-----------------------------------------------+")
    print(f"\n  Platform: {sys.platform}")
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Check rocm-smi
    import subprocess
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            print(f"  ROCm GPU: {' '.join(result.stdout.split()[:3])}")
        else:
            print("  ROCm GPU: not detected")
    except FileNotFoundError:
        print("  ROCm GPU: rocm-smi not found")
    except Exception as e:
        print(f"  ROCm GPU: {e}")

    print()

    check_rocm_provider()
    check_fireworks_provider()
    check_model_manager()
    check_gemma_prompt()
    check_routing()
    await check_live_generation()
    check_dockerfile()
    check_demo_wizard()

    print(f"\n  {'─'*44}")
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print(f"  {'─'*44}")
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
