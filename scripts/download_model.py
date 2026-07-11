#!/usr/bin/env python3
"""CLI to download GGUF models for ROCm local inference.

Usage:
    python scripts/download_model.py list
    python scripts/download_model.py download <name> [--output-dir PATH]
    python scripts/download_model.py status
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.settings.config import settings  # noqa: E402
from app.llm.model_manager import (  # noqa: E402
    download_model,
    get_model_info,
    list_catalogue,
    list_local_models,
)


def _progress_bar(downloaded: int, total: int) -> None:
    if total == 0:
        return
    pct = downloaded / total * 100
    bar_len = 40
    filled = int(bar_len * downloaded / total)
    bar = "#" * filled + "." * (bar_len - filled)
    mb_d = downloaded / 1_024 / 1_024
    mb_t = total / 1_024 / 1_024
    print(f"\r  {bar} {pct:5.1f}%  {mb_d:.1f}/{mb_t:.1f} MB", end="", flush=True)
    if downloaded >= total:
        print()


def cmd_list() -> None:
    """List all available models in the catalogue."""
    print(f"\n{'Name':<22} {'File':<38} {'Context':>7}")
    print("-" * 72)
    for m in list_catalogue():
        print(f"{m.name:<22} {m.filename:<38} {m.context_window:>7}")


def cmd_status() -> None:
    """Show which models are already downloaded."""
    models_dir = getattr(settings, "ROCm_MODELS_DIR", "./models/rocm")
    local = list_local_models(models_dir)
    print(f"\nModels directory: {models_dir}\n")
    print(f"{'Name':<22} {'Status':<12} {'Size':>8}")
    print("-" * 44)
    for m in local:
        status = "✓ Downloaded" if m["downloaded"] else "— Not present"
        size = f"{m['size_mb']:.1f} MB" if m["downloaded"] else ""
        print(f"{m['name']:<22} {status:<12} {size:>8}")


async def cmd_download(name: str, output_dir: str | None) -> None:
    """Download a single model by name."""
    info = get_model_info(name)
    if not info:
        print(f"Unknown model: {name!r}")
        print(f"Available: {', '.join(m.name for m in list_catalogue())}")
        sys.exit(1)

    out = output_dir or getattr(settings, "ROCm_MODELS_DIR", "./models/rocm")
    print(f"Downloading {info.name} ({info.filename}) …")
    print(f"  Source: huggingface.co/{info.hf_repo}")
    print(f"  Destination: {out}")
    try:
        path = await download_model(info, out, progress_callback=_progress_bar)
        size_mb = path.stat().st_size / 1_024 / 1_024
        print(f"\nDone — {size_mb:.1f} MB saved to {path}")
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download GGUF models for ROCm inference")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all available models")

    sub.add_parser("status", help="Show downloaded models")

    dl = sub.add_parser("download", help="Download a model")
    dl.add_argument("name", help="Model name (see `list`)")
    dl.add_argument("--output-dir", "-o", help="Output directory (default: ROCm_MODELS_DIR)")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list()
    elif args.command == "status":
        cmd_status()
    elif args.command == "download":
        asyncio.run(cmd_download(args.name, args.output_dir))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
