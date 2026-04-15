"""
OCR provider abstraction for the Adaptive RAG Clinical Assistant.

Provides a unified interface for optical character recognition across
local (Surya) and cloud (OpenAI Vision) backends.
"""

from .base import OCRProvider, OCRResult
from .factory import OCRFactory

__all__ = ["OCRFactory", "OCRProvider", "OCRResult"]
