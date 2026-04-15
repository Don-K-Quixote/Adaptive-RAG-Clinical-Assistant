"""
LLM Provider Factory.

Creates appropriate LLM provider instances based on configuration.
Supports both cloud (OpenAI) and local (Ollama) providers.
"""

import logging

from .base import LLMProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory class for creating LLM provider instances.

    Usage:
        # From config dict
        llm = LLMFactory.create({"provider": "ollama", "model": "llama3.1"})

        # Quick creation
        llm = LLMFactory.create_openai("gpt-4")
        llm = LLMFactory.create_ollama("biomistral")
    """

    PROVIDERS = {
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
    }

    # Default configurations
    DEFAULTS = {
        "openai": {
            "model": "gpt-4",
        },
        "ollama": {
            "model": "llama3.1:8b",
            "num_ctx": 4096,
        },
    }

    @classmethod
    def create(cls, config: dict) -> LLMProvider:
        """
        Create an LLM provider from configuration.

        Args:
            config: Configuration dictionary with keys:
                - provider: "openai" or "ollama"
                - model: Model name
                - Additional provider-specific options

        Returns:
            Configured LLMProvider instance

        Raises:
            ValueError: If provider is unknown
        """
        provider_name = config.get("provider", "ollama").lower()

        if provider_name not in cls.PROVIDERS:
            raise ValueError(
                f"Unknown provider: '{provider_name}'. Available: {list(cls.PROVIDERS.keys())}"
            )

        provider_class = cls.PROVIDERS[provider_name]
        defaults = cls.DEFAULTS.get(provider_name, {})

        # Merge defaults with provided config
        merged_config = {**defaults, **config}
        merged_config.pop("provider", None)  # Remove provider key

        logger.info(f"Creating {provider_name} provider with model: {merged_config.get('model')}")

        return provider_class(**merged_config)

    @classmethod
    def create_openai(cls, model: str = "gpt-4", api_key: str | None = None) -> OpenAIProvider:
        """
        Quick creation of OpenAI provider.

        Args:
            model: OpenAI model name
            api_key: Optional API key (defaults to env var)

        Returns:
            Configured OpenAIProvider
        """
        return OpenAIProvider(model=model, api_key=api_key)

    @classmethod
    def create_ollama(cls, model: str = "llama3.1:8b", num_ctx: int = 4096) -> OllamaProvider:
        """
        Quick creation of Ollama provider.

        Args:
            model: Model name or alias
            num_ctx: Context window size

        Returns:
            Configured OllamaProvider
        """
        return OllamaProvider(model=model, num_ctx=num_ctx)

    @classmethod
    def create_for_medical(cls, local: bool = True) -> LLMProvider:
        """
        Create a provider optimized for medical/clinical content.

        Args:
            local: If True, use local MedGemma; if False, use GPT-4o

        Returns:
            LLMProvider configured for medical domain
        """
        if local:
            return cls.create_ollama(model="medgemma")
        else:
            return cls.create_openai(model="gpt-4o")

    @classmethod
    def create_for_vision(cls, model: str = "llava:7b") -> OllamaProvider:
        """
        Create a provider for vision tasks (image analysis).

        Args:
            model: Vision model name

        Returns:
            OllamaProvider with vision capability
        """
        provider = cls.create_ollama(model=model)
        if not provider.supports_vision:
            raise ValueError(f"Model '{model}' does not support vision")
        return provider

    @classmethod
    def get_available_providers(cls) -> dict:
        """
        Get information about available providers and their status.

        Returns:
            Dict with provider info and availability status
        """
        status = {}

        for name, provider_class in cls.PROVIDERS.items():
            try:
                defaults = cls.DEFAULTS.get(name, {})
                provider = provider_class(**defaults)
                available = provider.is_available()
                model_info = provider.get_model_info()

                status[name] = {
                    "available": available,
                    "default_model": defaults.get("model"),
                    "local": model_info.get("local", False),
                    "models": cls._get_available_models(name, provider),
                }
            except Exception as e:
                status[name] = {"available": False, "error": str(e)}

        return status

    @classmethod
    def _get_available_models(cls, provider_name: str, provider: LLMProvider) -> list:
        """Get list of available models for a provider."""
        if provider_name == "ollama":
            return provider.list_available_models()
        elif provider_name == "openai":
            return list(OpenAIProvider.MODELS.keys())
        return []


def get_llm(provider: str = "ollama", model: str | None = None, **kwargs) -> LLMProvider:
    """
    Convenience function to get an LLM provider.

    Args:
        provider: "openai" or "ollama"
        model: Model name (optional, uses default)
        **kwargs: Additional provider-specific options

    Returns:
        Configured LLMProvider

    Example:
        llm = get_llm("ollama", "biomistral")
        response = llm.generate("What is RECIST 1.1?")
    """
    config = {"provider": provider, **kwargs}
    if model:
        config["model"] = model
    return LLMFactory.create(config)
