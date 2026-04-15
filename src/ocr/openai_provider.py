"""
Cloud OCR provider backed by OpenAI Vision (gpt-4o / gpt-4o-mini).

Converts a PIL Image to a base64-encoded PNG and sends it to the
OpenAI chat completions API using the image_url content type.

The openai package is already in the project environment, so no extra
install is needed.  An API key must be supplied or set via OPENAI_API_KEY.
"""

import base64
import io
import logging
import os

import PIL.Image

from .base import OCRProvider, OCRResult

logger = logging.getLogger(__name__)

_OCR_SYSTEM_PROMPT = (
    "Extract all text exactly as it appears. "
    "Preserve table structure using markdown. "
    "Return only the extracted text."
)

# Models that support vision input
_VISION_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-turbo-preview"}


class OpenAIVisionProvider(OCRProvider):
    """OCR provider that calls the OpenAI Vision API.

    Args:
        model: OpenAI model ID. Must support vision (e.g. gpt-4o, gpt-4o-mini).
        api_key: OpenAI API key. Defaults to the OPENAI_API_KEY environment variable.

    Note:
        OpenAI does not expose per-token confidence scores, so OCRResult.confidence
        is always set to -1.0 for this provider.
    """

    def __init__(self, model: str = "gpt-4o", api_key: str = "") -> None:
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._client = None

        if model not in _VISION_MODELS:
            logger.warning(
                f"Model '{model}' may not support vision input. "
                f"Recommended: {sorted(_VISION_MODELS)}"
            )

    @property
    def _openai_client(self):
        """Lazy-initialise the OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @staticmethod
    def _image_to_base64(image: PIL.Image.Image) -> str:
        """Encode a PIL Image as a base64 PNG string."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def ocr_image(self, image: PIL.Image.Image, page_index: int) -> OCRResult:
        """Extract text from a page image via OpenAI Vision.

        Args:
            image: PIL Image of the page.
            page_index: Zero-based page index for metadata.

        Returns:
            OCRResult with extracted text; confidence is always -1.0.

        Raises:
            ValueError: If no API key is configured.
            openai.OpenAIError: On API failure.
        """
        if not self.api_key:
            raise ValueError(
                "OpenAI API key is not set. "
                "Pass api_key= or set the OPENAI_API_KEY environment variable."
            )

        b64_image = self._image_to_base64(image)

        response = self._openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64_image}",
                                "detail": "high",
                            },
                        }
                    ],
                },
            ],
            max_tokens=4096,
        )

        text = response.choices[0].message.content or ""
        logger.debug(f"OpenAI Vision OCR page {page_index}: {len(text)} chars extracted")

        return OCRResult(
            text=text,
            confidence=-1.0,
            page_index=page_index,
            provider=self.provider_name,
        )

    def is_available(self) -> bool:
        """Return True when an API key is configured."""
        return bool(self.api_key)

    @property
    def provider_name(self) -> str:
        return "openai"
