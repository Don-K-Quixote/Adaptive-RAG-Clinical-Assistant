"""
Factory for creating OCR provider instances.

Usage:
    provider = OCRFactory.create("surya")
    provider = OCRFactory.create("openai", model="gpt-4o-mini", api_key="sk-...")
"""

from .base import OCRProvider
from .openai_provider import OpenAIVisionProvider
from .surya_provider import SuryaProvider


class OCRFactory:
    """Create OCR provider instances by name."""

    @staticmethod
    def create(provider: str, model: str = "gpt-4o", api_key: str = "") -> OCRProvider:
        """Instantiate the requested OCR provider.

        Args:
            provider: Provider name — "surya" or "openai".
            model: Model name; only used by the OpenAI provider.
            api_key: API key; only used by the OpenAI provider.

        Returns:
            Configured OCRProvider instance.

        Raises:
            ValueError: If the provider name is not recognised.
        """
        if provider == "surya":
            return SuryaProvider()
        if provider == "openai":
            return OpenAIVisionProvider(model=model, api_key=api_key)
        raise ValueError(
            f"Unknown OCR provider: '{provider}'. Supported values: 'surya', 'openai'."
        )
