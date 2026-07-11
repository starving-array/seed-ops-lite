"""Model management — download, list, verify GGUF models for local inference."""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("safeseedops.llm.model_manager")


@dataclass
class ModelInfo:
    """Metadata for a downloadable GGUF model."""

    name: str
    """Short name used in code (e.g. ``gemma-2-9b-it``)."""

    filename: str
    """GGUF file name on disk (e.g. ``gemma-2-9b-it-Q4_K_M.gguf``)."""

    hf_repo: str
    """Hugging Face repo (e.g. ``TheBloke/gemma-2-9b-it-GGUF``)."""

    hf_file: str
    """File name inside the HF repo."""

    sha256: str | None = None
    """Optional SHA-256 checksum for verification."""

    context_window: int = 8192
    """Maximum context length supported."""

    supports_json: bool = True
    """Whether the model handles JSON mode well."""


# ── Catalogue ──────────────────────────────────────────────────────────

CATALOGUE: list[ModelInfo] = [
    ModelInfo(
        name="gemma-2-2b-it",
        filename="gemma-2-2b-it-Q4_K_M.gguf",
        hf_repo="bartowski/gemma-2-2b-it-GGUF",
        hf_file="gemma-2-2b-it-Q4_K_M.gguf",
        context_window=8192,
    ),
    ModelInfo(
        name="gemma-2-9b-it",
        filename="gemma-2-9b-it-Q4_K_M.gguf",
        hf_repo="bartowski/gemma-2-9b-it-GGUF",
        hf_file="gemma-2-9b-it-Q4_K_M.gguf",
        context_window=8192,
    ),
    ModelInfo(
        name="gemma-3-12b-it",
        filename="gemma-3-12b-it-Q4_K_M.gguf",
        hf_repo="bartowski/gemma-3-12b-it-GGUF",
        hf_file="gemma-3-12b-it-Q4_K_M.gguf",
        context_window=32768,
    ),
    ModelInfo(
        name="llama-3.2-3b",
        filename="llama-3.2-3b-instruct-Q4_K_M.gguf",
        hf_repo="bartowski/Llama-3.2-3B-Instruct-GGUF",
        hf_file="Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        context_window=8192,
    ),
]


def get_model_info(name: str) -> ModelInfo | None:
    """Look up model metadata by short name."""
    for m in CATALOGUE:
        if m.name == name:
            return m
    return None


def list_catalogue() -> list[ModelInfo]:
    """Return all known models."""
    return list(CATALOGUE)


# ── Download ────────────────────────────────────────────────────────────

_HF_BASE = "https://huggingface.co"


def download_url(model: ModelInfo) -> str:
    """Hugging Face download URL for the GGUF file."""
    return f"{_HF_BASE}/{model.hf_repo}/resolve/main/{model.hf_file}"


async def download_model(
    model: ModelInfo,
    output_dir: str | Path,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
    timeout: float = 600.0,
) -> Path:
    """Download a GGUF model file from Hugging Face.

    Args:
        model: Model metadata from the catalogue.
        output_dir: Directory to save the file into (created if missing).
        progress_callback: Called with ``(downloaded_bytes, total_bytes)``.
        timeout: Total timeout in seconds (default 10 minutes).

    Returns:
        Path to the downloaded file.

    Raises:
        FileNotFoundError: If the download fails (HTTP error).
        httpx.TimeoutException: If the download times out.
    """
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    file_path = dest / model.filename

    url = download_url(model)
    logger.info("Downloading %s from %s", model.name, url)

    async with (
        httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client,
        client.stream("GET", url, follow_redirects=True) as resp,
    ):
        if resp.status_code != 200:
            raise FileNotFoundError(
                f"Failed to download {model.name}: HTTP {resp.status_code}"
            )

            total = int(resp.headers.get("content-length", 0))
            downloaded: int = 0

            with open(file_path, "wb") as f:  # noqa: ASYNC101, PTH123
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

    logger.info("Downloaded %s (%.1f MB)", model.name, downloaded / 1_024 / 1_024)
    return file_path


# ── Verification ───────────────────────────────────────────────────────


def verify_checksum(file_path: str | Path, expected_sha256: str) -> bool:
    """Verify SHA-256 checksum of a downloaded file."""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:  # noqa: PTH123
        while True:
            block = f.read(65536)
            if not block:
                break
            sha.update(block)
    return sha.hexdigest().lower() == expected_sha256.lower()


# ─── Local disk helpers ────────────────────────────────────────────────


def list_local_models(models_dir: str | Path) -> list[dict[str, Any]]:
    """Scan a directory and report which catalogue models exist on disk."""
    d = Path(models_dir)
    if not d.is_dir():
        return []
    models: list[dict[str, Any]] = []
    for info in CATALOGUE:
        path = d / info.filename
        models.append(
            {
                "name": info.name,
                "filename": info.filename,
                "downloaded": path.exists(),
                "size_mb": (
                    round(path.stat().st_size / 1_024 / 1_024, 1)
                    if path.exists()
                    else 0
                ),
                "context_window": info.context_window,
            }
        )
    return models
