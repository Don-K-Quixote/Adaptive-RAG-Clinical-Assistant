"""
Abstract base for OCR providers.

Defines the contract that all OCR backends (Surya, OpenAI Vision, …) must fulfil,
plus the shared OCRResult dataclass returned by every provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import PIL.Image


@dataclass
class OCRResult:
    """Standardized output from any OCR provider.

    Args:
        text: Extracted text content from the page.
        confidence: Aggregate confidence score in [0.0, 1.0].
            Use -1.0 when the provider does not expose per-line confidence.
        page_index: Zero-based index of the source PDF page.
        provider: Short identifier of the OCR backend (e.g. "surya", "openai").
    """

    text: str
    confidence: float
    page_index: int
    provider: str


class OCRProvider(ABC):
    """Interface that every OCR backend must implement."""

    @abstractmethod
    def ocr_image(self, image: PIL.Image.Image, page_index: int) -> OCRResult:
        """Run OCR on a single page image.

        Args:
            image: PIL Image of the page (typically rendered at 200 dpi).
            page_index: Zero-based page index; stored verbatim in OCRResult.

        Returns:
            OCRResult with extracted text and metadata.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the provider can be used without errors.

        For local providers this means the package is installed.
        For cloud providers this means a valid API key is configured.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short, stable identifier for this backend (e.g. "surya")."""
