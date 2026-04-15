"""
Ollama LLM Provider implementation.

Supports local models including Llama 3.1, Mistral, BioMistral, MedGemma, Gemma 2, Phi-3, and LLaVA.
Runs entirely offline after initial model download.
"""

import base64
import logging
import time
from collections.abc import Iterator
from pathlib import Path

from .base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.

    Requires Ollama to be installed and running locally.
    Models must be pulled before use: `ollama pull <model_name>`
    """

    # Available models with their configurations
    # These are the correct model names as verified with Ollama
    MODELS = {
        # Text models
        "llama3.1:8b": {
            "context_window": 8192,
            "supports_vision": False,
            "description": "Meta's Llama 3.1 8B - Best general performance",
        },
        "mistral:7b": {
            "context_window": 8192,
            "supports_vision": False,
            "description": "Mistral 7B - Fast and efficient",
        },
        "adrienbrault/biomistral-7b:Q4_K_M": {
            "context_window": 32768,
            "supports_vision": False,
            "description": "BioMistral 7B - Medical domain fine-tuned",
        },
        "cniongolo/biomistral": {
            "context_window": 32768,
            "supports_vision": False,
            "description": "BioMistral (alternative) - Medical domain",
        },
        "gemma2:9b": {
            "context_window": 8192,
            "supports_vision": False,
            "description": "Google Gemma 2 9B - Strong reasoning",
        },
        "phi3:mini": {
            "context_window": 4096,
            "supports_vision": False,
            "description": "Microsoft Phi-3 Mini - Compact and fast",
        },
        "alibayram/medgemma:4b": {
            "context_window": 8192,
            "supports_vision": True,
            "description": "Google MedGemma 4B - Medical domain specialized (Gemma 3 variant)",
        },
        # Vision models
        "llava:7b": {
            "context_window": 4096,
            "supports_vision": True,
            "description": "LLaVA 7B - Vision-language model",
        },
        "llava:13b": {
            "context_window": 4096,
            "supports_vision": True,
            "description": "LLaVA 13B - Larger vision model",
        },
        "moondream": {
            "context_window": 2048,
            "supports_vision": True,
            "description": "Moondream - Lightweight vision model",
        },
        "bakllava": {
            "context_window": 4096,
            "supports_vision": True,
            "description": "BakLLaVA - Mistral-based vision model",
        },
    }

    # Friendly aliases for easier configuration
    MODEL_ALIASES = {
        "llama3.1": "llama3.1:8b",
        "llama3": "llama3.1:8b",
        "mistral": "mistral:7b",
        "biomistral": "adrienbrault/biomistral-7b:Q4_K_M",
        "gemma2": "gemma2:9b",
        "gemma": "gemma2:9b",
        "phi3": "phi3:mini",
        "phi": "phi3:mini",
        "medgemma": "alibayram/medgemma:4b",
        "medgemma4b": "alibayram/medgemma:4b",
        "llava": "llava:7b",
    }

    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
        num_ctx: int = 4096,
        num_gpu: int = -1,  # -1 = auto, use all available GPU layers
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Model name or alias
            host: Ollama server URL
            num_ctx: Context window size (tokens)
            num_gpu: Number of GPU layers (-1 for auto)
        """
        # Resolve alias to full model name
        self.model = self.MODEL_ALIASES.get(model, model)
        self.host = host
        self.num_ctx = num_ctx
        self.num_gpu = num_gpu
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Ollama client."""
        if self._client is None:
            try:
                import ollama

                self._client = ollama
            except ImportError as err:
                raise ImportError("Ollama package not installed. Run: pip install ollama") from err
        return self._client

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float | None = None,
    ) -> str:
        """Generate a response from Ollama."""
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

        options: dict = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": self.num_ctx,
            "num_gpu": self.num_gpu,
        }
        if top_p is not None:
            options["top_p"] = top_p

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options=options,
            )

            latency_ms = (time.time() - start_time) * 1000

            # Extract token counts if available
            tokens_used = None
            if "eval_count" in response:
                tokens_used = response.get("prompt_eval_count", 0) + response.get("eval_count", 0)

            return LLMResponse(
                content=response["message"]["content"],
                model=self.model,
                provider="ollama",
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        top_p: float | None = None,
    ) -> Iterator[str]:
        """Stream a response token-by-token from Ollama."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        options: dict = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": self.num_ctx,
            "num_gpu": self.num_gpu,
        }
        if top_p is not None:
            options["top_p"] = top_p

        try:
            stream = self.client.chat(
                model=self.model,
                messages=messages,
                options=options,
                stream=True,
            )
            for chunk in stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            raise

    def generate_with_image(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate a response with an image input.

        Args:
            prompt: Text prompt
            image_path: Path to image file
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum response tokens

        Returns:
            Generated text response

        Raises:
            ValueError: If model doesn't support vision
        """
        if not self.supports_vision:
            raise ValueError(
                f"Model '{self.model}' does not support vision. "
                f"Use a vision model like 'llava:7b' or 'moondream'"
            )

        # Read and encode image
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt, "images": [image_data]})

        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "num_ctx": self.num_ctx,
                },
            )
            return response["message"]["content"]

        except Exception as e:
            logger.error(f"Ollama vision error: {e}")
            raise

    def get_model_info(self) -> dict:
        """Get model information."""
        model_config = self.MODELS.get(self.model, {})
        return {
            "provider": "ollama",
            "model": self.model,
            "local": True,
            "context_window": model_config.get("context_window", 4096),
            "supports_vision": model_config.get("supports_vision", False),
            "description": model_config.get("description", "Unknown model"),
        }

    def is_available(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            # Check if Ollama is running
            available_models = self.list_available_models()

            if not available_models:
                logger.warning("No models found in Ollama")
                return False

            # Check exact match or partial match
            model_available = any(
                self.model in m or m.startswith(self.model.split(":")[0]) for m in available_models
            )

            if not model_available:
                logger.warning(
                    f"Model '{self.model}' not found. "
                    f"Available: {available_models}. "
                    f"Run: ollama pull {self.model}"
                )
                return False

            return True

        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    def list_available_models(self) -> list[str]:
        """List all models currently downloaded in Ollama."""
        try:
            response = self.client.list()

            # Handle different response formats from ollama package versions
            # Newer versions return a ListResponse object with 'models' attribute
            # Older versions return a dict with 'models' key
            if hasattr(response, "models"):
                # Newer ollama package version (ListResponse object)
                models = response.models
                return [m.model if hasattr(m, "model") else str(m) for m in models]
            elif isinstance(response, dict):
                # Older ollama package version (dict)
                models = response.get("models", [])
                return [m.get("name", str(m)) for m in models]
            else:
                # Fallback: try to iterate
                return [str(m) for m in response]

        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    @property
    def supports_vision(self) -> bool:
        """Check if current model supports vision."""
        model_config = self.MODELS.get(self.model, {})
        return model_config.get("supports_vision", False)

    @classmethod
    def get_recommended_models(cls) -> dict:
        """Get recommended models for different use cases."""
        return {
            "general": {"model": "llama3.1:8b", "reason": "Best balance of quality and speed"},
            "medical": {
                "model": "alibayram/medgemma:4b",
                "reason": "Google's medical-domain Gemma 3 variant, trained on clinical text",
            },
            "medical_alt": {
                "model": "adrienbrault/biomistral-7b:Q4_K_M",
                "reason": "BioMistral fine-tuned on medical literature (alternative)",
            },
            "fast": {"model": "phi3:mini", "reason": "Fastest inference, good for simple queries"},
            "vision": {"model": "llava:7b", "reason": "Best vision-language model for 8GB VRAM"},
        }
