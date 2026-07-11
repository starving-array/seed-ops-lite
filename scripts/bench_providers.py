#!/usr/bin/env python3
"""Compare LLM output quality & performance across providers.

Usage:
    python scripts/bench_providers.py                        # test all available providers
    python scripts/bench_providers.py --providers gemini,fireworks  # specific providers
    python scripts/bench_providers.py --prompt "Say hello"    # custom prompt
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.config_resolver import resolve_llm_config  # noqa: E402
from app.llm.gateway import LLMGateway  # noqa: E402
from app.llm.models import LLMRequest  # noqa: E402
from app.llm.provider import provider_registry  # noqa: E402

_DEFAULT_PROMPT = """Generate 3 rows of synthetic customer data with columns: id, name, email, signup_date.
Return ONLY valid JSON as an array of objects."""


def _available_providers() -> list[str]:
    """Return names of providers that are available right now."""
    result: list[str] = []
    for name in ["vertex", "gemini", "anthropic", "openai", "fireworks", "rocm", "ollama"]:
        try:
            p = provider_registry.getProvider(name)
            if p.is_available():
                result.append(name)
            else:
                print(f"  ╰─ {name}: skipped ({p.auth_status()})")
        except Exception:
            continue
    return result


async def bench_one(gateway: LLMGateway, provider: str, prompt: str) -> dict:
    """Run a single generation and return metrics."""
    request = LLMRequest(prompt=prompt, max_tokens=512, temperature=0.2)
    start = time.perf_counter()
    try:
        resp = await gateway.generate(request)
        latency = (time.perf_counter() - start) * 1000
        return {
            "provider": provider,
            "success": True,
            "latency_ms": round(latency, 1),
            "tokens": resp.usage.total_tokens or 0,
            "cost": resp.usage.estimated_cost or 0.0,
            "text_preview": resp.text[:120].replace("\n", " "),
        }
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        return {
            "provider": provider,
            "success": False,
            "latency_ms": round(latency, 1),
            "tokens": 0,
            "cost": 0.0,
            "error": str(exc),
        }


async def main(providers: list[str] | None, prompt: str) -> None:
    print("=" * 64)
    print("  LLM Provider Benchmark")
    print("=" * 64)
    print(f"\nPrompt: {prompt[:100]}{'…' if len(prompt) > 100 else ''}")
    print()

    if providers:
        targets = providers
    else:
        print("Scanning available providers …")
        targets = _available_providers()

    if not targets:
        print("No available providers found.")
        sys.exit(1)

    print(f"\nTesting {len(targets)} provider(s): {', '.join(targets)}\n")

    gateway = LLMGateway()
    results = await asyncio.gather(*[bench_one(gateway, p, prompt) for p in targets])

    print()
    print("-" * 64)
    print(f"{'Provider':<20} {'Latency':>10} {'Tokens':>8} {'Cost':>10}  Status")
    print("-" * 64)
    for r in results:
        status = "[OK]" if r["success"] else "[FAIL]"
        lat = f"{r['latency_ms']:.0f} ms" if r["success"] else "—"
        tok = str(r["tokens"]) if r["success"] else "—"
        cost = f"${r['cost']:.6f}" if r["success"] else "—"
        print(f"{r['provider']:<20} {lat:>10} {tok:>8} {cost:>10}  {status}")
        if not r["success"]:
            print(f"  ╰─ {r['error'][:100]}")
    print("-" * 64)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark LLM providers")
    parser.add_argument(
        "--providers",
        help="Comma-separated provider names (default: auto-detect)",
    )
    parser.add_argument("--prompt", default=_DEFAULT_PROMPT, help="Test prompt")
    args = parser.parse_args()

    providers_list = args.providers.split(",") if args.providers else None
    asyncio.run(main(providers_list, args.prompt))
