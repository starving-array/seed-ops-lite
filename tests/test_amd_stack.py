"""Integration tests for the AMD ROCm + Fireworks stack."""

import sys

import pytest

from app.llm.provider import provider_registry


class TestROCmProvider:
    """ROCm provider unit tests (platform-independent)."""

    def test_registered(self) -> None:
        p = provider_registry.getProvider("rocm")
        assert p.name() == "ROCm"

    def test_supported_models_include_gemma(self) -> None:
        p = provider_registry.getProvider("rocm")
        models = p.supported_models()
        assert any("gemma" in m for m in models), "Expected at least one Gemma model"

    def test_estimate_cost_zero(self) -> None:
        p = provider_registry.getProvider("rocm")
        assert p.estimateCost("gemma-2-9b-it", 100, 50) == 0.0

    def test_auth_status_platform(self) -> None:
        p = provider_registry.getProvider("rocm")
        status = p.auth_status()
        if sys.platform == "linux":
            assert "AMD GPU" in status or "roc" in status.lower()
        else:
            assert "requires Linux" in status

    def test_capabilities(self) -> None:
        p = provider_registry.getProvider("rocm")
        caps = p.capabilities()
        assert caps["json_mode"] is True
        assert caps["streaming"] is True
        assert caps["tool_calling"] is False


class TestFireworksProvider:
    """Fireworks provider unit tests."""

    def test_registered(self) -> None:
        p = provider_registry.getProvider("fireworks")
        assert p.name() == "Fireworks AI"

    def test_supported_models_include_gemma(self) -> None:
        p = provider_registry.getProvider("fireworks")
        models = p.supported_models()
        assert any("gemma" in m for m in models), "Expected Gemma model on Fireworks"

    def test_capabilities(self) -> None:
        p = provider_registry.getProvider("fireworks")
        caps = p.capabilities()
        assert caps["json_mode"] is True
        assert caps["tool_calling"] is True


class TestModelManager:
    """Model manager unit tests."""

    def test_catalogue_contains_gemma(self) -> None:
        from app.llm.model_manager import list_catalogue

        names = [m.name for m in list_catalogue()]
        assert "gemma-2-9b-it" in names
        assert "gemma-3-12b-it" in names

    def test_catalogue_lookup(self) -> None:
        from app.llm.model_manager import get_model_info

        info = get_model_info("gemma-2-9b-it")
        assert info is not None
        assert info.filename == "gemma-2-9b-it-Q4_K_M.gguf"
        assert info.hf_repo == "TheBloke/gemma-2-9b-it-GGUF"

    def test_download_url_format(self) -> None:
        from app.llm.model_manager import download_url, get_model_info

        info = get_model_info("gemma-2-9b-it")
        url = download_url(info)
        assert "huggingface.co" in url
        assert info.filename in url

    def test_list_local_models_empty(self, tmp_path) -> None:
        from app.llm.model_manager import list_local_models

        result = list_local_models(tmp_path)
        assert isinstance(result, list)
        for m in result:
            assert not m["downloaded"]


class TestGemmaPromptFormat:
    """Gemma chat template formatting tests."""

    def test_format_gemma_prompt(self) -> None:
        from app.llm.provider import _format_gemma_prompt

        result = _format_gemma_prompt("Say hello")
        assert "<start_of_turn>user" in result
        assert "<end_of_turn>" in result
        assert "<start_of_turn>model" in result
        assert result.endswith("\n")

    def test_format_gemma_prompt_json_mode(self) -> None:
        from app.llm.provider import _format_gemma_prompt

        result = _format_gemma_prompt("Generate JSON", json_mode=True)
        assert "JSON generator" in result
        assert "valid JSON" in result
        assert "<start_of_turn>user" in result


class TestAutoRouting:
    """Model-aware routing tests."""

    def test_gemma_routing_order(self) -> None:
        from app.llm.gateway import _resolve_routing_order

        fallback = [
            "vertex",
            "gemini",
            "anthropic",
            "openai",
            "fireworks",
            "rocm",
            "ollama",
        ]
        order = _resolve_routing_order("gemma-2-9b-it", fallback)
        # ROCm and Fireworks should be first
        assert order.index("rocm") < order.index("vertex")
        assert order.index("fireworks") < order.index("vertex")

    def test_non_gemma_routing_unchanged(self) -> None:
        from app.llm.gateway import _resolve_routing_order

        fallback = [
            "vertex",
            "gemini",
            "anthropic",
            "openai",
            "fireworks",
            "rocm",
            "ollama",
        ]
        order = _resolve_routing_order("gpt-4o", fallback)
        assert order == fallback


class TestProviderRegistry:
    """Registry duplicate protection tests."""

    def test_duplicate_registration_raises(self) -> None:
        from app.llm.exceptions import LLMConfigurationError
        from app.llm.provider import FireworksProvider, ProviderRegistry

        r = ProviderRegistry()
        with pytest.raises(LLMConfigurationError, match="already registered"):
            r.register("fireworks", FireworksProvider())

    def test_unregister_then_register(self) -> None:
        from app.llm.provider import FireworksProvider, ProviderRegistry

        r = ProviderRegistry()
        r.unregister("fireworks")
        # Should not raise now
        r.register("fireworks", FireworksProvider())
        assert r.getProvider("fireworks").name() == "Fireworks AI"
