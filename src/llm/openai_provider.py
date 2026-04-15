"""
OpenAI LLM Provider implementation.

Supports GPT-4, GPT-4-Turbo, GPT-3.5-Turbo, and other OpenAI models.
"""

import logging
import os
import time
from collections.abc import Iterator

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider for GPT models.

    Requires OPENAI_API_KEY environment variable or explicit api_key parameter.
    """

    # Model configurations
    MODELS = {
        "gpt-4": {"context_window": 8192, "supports_vision": False},
        "gpt-4-turbo": {"context_window": 128000, "supports_vision": True},
        "gpt-4-turbo-preview": {"context_window": 128000, "supports_vision": False},
        "gpt-4o": {"context_window": 128000, "supports_vision": True},
        "gpt-4o-mini": {"context_window": 128000, "supports_vision": True},
        "gpt-3.5-turbo": {"context_window": 16385, "supports_vision": False},
    }

    def __init__(
        self, model: str = "gpt-4", api_key: str | None = None, base_url: str | None = None
    ):
        """
        Initialize OpenAI provider.

        Args:
            model: Model name (default: gpt-4)
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            base_url: Optional custom base URL for API
        """
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self._client = None

        if model not in self.MODELS:
            logger.warning(f"Unknown model '{model}', using default settings")

    @property
    def client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError as err:
                raise ImportError("OpenAI package not installed. Run: pip install openai") from err
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float | None = None,
    ) -> str:
        """Generate a response from OpenAI."""
        response = self.generate_with_metadata(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
        )
        return response.content

    def generate_with_metadata(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float | None = None,
    ) -> LLMResponse:
        """Generate a response with metadata."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        start_time = time.time()

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if top_p is not None:
            kwargs["top_p"] = top_p

        try:
            response = self.client.chat.completions.create(**kwargs)

            latency_ms = (time.time() - start_time) * 1000

            return LLMResponse(
                content=response.choices[0].message.content,
                model=self.model,
                provider="openai",
                tokens_used=response.usage.total_tokens if response.usage else None,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float | None = None,
    ) -> Iterator[str]:
        """Stream a response token-by-token from OpenAI."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if top_p is not None:
            kwargs["top_p"] = top_p

        try:
            stream = self.client.chat.completions.create(**kwargs)
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    def get_model_info(self) -> dict:
        """Get model information."""
        model_config = self.MODELS.get(self.model, {})
        return {
            "provider": "openai",
            "model": self.model,
            "local": False,
            "context_window": model_config.get("context_window", 8192),
            "supports_vision": model_config.get("supports_vision", False),
        }

    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            return False

        try:
            # Quick test call
            self.client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI API not available: {e}")
            return False

    @property
    def supports_vision(self) -> bool:
        """Check if current model supports vision."""
        model_config = self.MODELS.get(self.model, {})
        return model_config.get("supports_vision", False)
