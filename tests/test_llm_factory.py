"""
Tests for LLM Factory and provider configuration.

Tests factory creation logic, alias resolution, and configuration merging.
Does NOT test live API calls (requires running services).
"""

import pytest

from src.llm.factory import LLMFactory
from src.llm.ollama_provider import OllamaProvider
from src.llm.openai_provider import OpenAIProvider


class TestLLMFactoryCreate:
    """Test LLMFactory.create() with different configs."""

    def test_create_ollama_provider(self):
        llm = LLMFactory.create({"provider": "ollama", "model": "llama3.1:8b"})
        assert isinstance(llm, OllamaProvider)
        assert llm.model == "llama3.1:8b"

    def test_create_openai_provider(self):
        llm = LLMFactory.create(
            {
                "provider": "openai",
                "model": "gpt-4o",
                "api_key": "test-key",
            }
        )
        assert isinstance(llm, OpenAIProvider)
        assert llm.model == "gpt-4o"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            LLMFactory.create({"provider": "anthropic"})

    def test_default_provider_is_ollama(self):
        llm = LLMFactory.create({})
        assert isinstance(llm, OllamaProvider)

    def test_defaults_applied_when_missing(self):
        """Factory should merge defaults when model not specified."""
        llm = LLMFactory.create({"provider": "ollama"})
        assert llm.model == "llama3.1:8b"  # from DEFAULTS


class TestOllamaAliases:
    """Test model alias resolution in OllamaProvider."""

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("llama3.1", "llama3.1:8b"),
            ("llama3", "llama3.1:8b"),
            ("mistral", "mistral:7b"),
            ("biomistral", "adrienbrault/biomistral-7b:Q4_K_M"),
            ("gemma2", "gemma2:9b"),
            ("phi3", "phi3:mini"),
            ("medgemma", "alibayram/medgemma:4b"),
            ("medgemma4b", "alibayram/medgemma:4b"),
            ("llava", "llava:7b"),
        ],
    )
    def test_alias_resolution(self, alias, expected):
        provider = OllamaProvider(model=alias)
        assert provider.model == expected

    def test_full_name_passthrough(self):
        """Full model names should not be aliased."""
        provider = OllamaProvider(model="adrienbrault/biomistral-7b:Q4_K_M")
        assert provider.model == "adrienbrault/biomistral-7b:Q4_K_M"

    def test_unknown_model_passthrough(self):
        """Unknown models should be used as-is (Ollama handles validation)."""
        provider = OllamaProvider(model="custom-model:latest")
        assert provider.model == "custom-model:latest"


class TestMedGemmaIntegration:
    """Verify MedGemma is properly registered."""

    def test_medgemma_in_ollama_models(self):
        assert "alibayram/medgemma:4b" in OllamaProvider.MODELS

    def test_medgemma_supports_vision(self):
        config = OllamaProvider.MODELS["alibayram/medgemma:4b"]
        assert config["supports_vision"] is True

    def test_medgemma_context_window(self):
        config = OllamaProvider.MODELS["alibayram/medgemma:4b"]
        assert config["context_window"] == 8192

    def test_medgemma_is_recommended_medical(self):
        recs = OllamaProvider.get_recommended_models()
        assert recs["medical"]["model"] == "alibayram/medgemma:4b"

    def test_factory_create_for_medical_local(self):
        llm = LLMFactory.create_for_medical(local=True)
        assert isinstance(llm, OllamaProvider)
        assert llm.model == "alibayram/medgemma:4b"

    def test_factory_create_for_medical_cloud(self):
        llm = LLMFactory.create_for_medical(local=False)
        assert isinstance(llm, OpenAIProvider)
        assert llm.model == "gpt-4o"


class TestQuickCreation:
    """Test convenience factory methods."""

    def test_create_openai(self):
        llm = LLMFactory.create_openai("gpt-4o-mini")
        assert isinstance(llm, OpenAIProvider)
        assert llm.model == "gpt-4o-mini"

    def test_create_ollama(self):
        llm = LLMFactory.create_ollama("gemma2", num_ctx=8192)
        assert isinstance(llm, OllamaProvider)
        assert llm.model == "gemma2:9b"  # alias resolved
        assert llm.num_ctx == 8192


class TestModelInfo:
    """Test model info and configuration."""

    def test_openai_model_info(self):
        llm = OpenAIProvider(model="gpt-4o", api_key="test")
        info = llm.get_model_info()
        assert info["provider"] == "openai"
        assert info["local"] is False
        assert info["context_window"] == 128000

    def test_ollama_model_info(self):
        llm = OllamaProvider(model="llama3.1:8b")
        info = llm.get_model_info()
        assert info["provider"] == "ollama"
        assert info["local"] is True
        assert info["context_window"] == 8192
