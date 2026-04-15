"""
Local OCR provider backed by Surya.

Surya is a multilingual OCR library that runs entirely on-device —
no API key or network connection required.  Models are heavy, so they
are lazy-loaded on the first call to ocr_image().

Install:
    pip install surya-ocr
"""

import logging

import PIL.Image

from .base import OCRProvider, OCRResult

logger = logging.getLogger(__name__)

_SURYA_AVAILABLE: bool | None = None  # cached import probe


def _check_surya() -> bool:
    global _SURYA_AVAILABLE
    if _SURYA_AVAILABLE is None:
        try:
            import surya.ocr  # noqa: F401

            _SURYA_AVAILABLE = True
        except ImportError:
            _SURYA_AVAILABLE = False
    return _SURYA_AVAILABLE


class SuryaProvider(OCRProvider):
    """OCR provider that uses the Surya local model.

    Models are downloaded on first use and then cached by Surya internally.
    English is used as the recognition language.
    """

    def __init__(self) -> None:
        self._det_model = None
        self._det_processor = None
        self._rec_model = None
        self._rec_processor = None

    def _load_models(self) -> None:
        """Lazy-load Surya detection and recognition models."""
        if self._rec_model is not None:
            return  # already loaded

        from surya.model.detection.model import load_model as load_det_model
        from surya.model.detection.processor import load_processor as load_det_processor
        from surya.model.recognition.model import load_model as load_rec_model
        from surya.model.recognition.processor import load_processor as load_rec_processor

        logger.info("Loading Surya OCR models (this may take a moment on first run)…")
        self._det_processor = load_det_processor()
        self._det_model = load_det_model()
        self._rec_processor = load_rec_processor()
        self._rec_model = load_rec_model()

    def ocr_image(self, image: PIL.Image.Image, page_index: int) -> OCRResult:
        """Run Surya OCR on a PIL image and return extracted text.

        Args:
            image: PIL Image of the page.
            page_index: Zero-based page index for metadata.

        Returns:
            OCRResult with joined line text and mean line confidence.

        Raises:
            ImportError: If surya-ocr is not installed.
        """
        if not _check_surya():
            raise ImportError("surya-ocr is not installed. Install it with: pip install surya-ocr")

        from surya.ocr import run_ocr

        self._load_models()

        results = run_ocr(
            [image],
            [["en"]],
            self._det_model,
            self._det_processor,
            self._rec_model,
            self._rec_processor,
        )

        page_result = results[0]
        lines = page_result.text_lines

        if not lines:
            return OCRResult(
                text="", confidence=0.0, page_index=page_index, provider=self.provider_name
            )

        text = "\n".join(line.text for line in lines)
        avg_confidence = sum(line.confidence for line in lines) / len(lines)

        return OCRResult(
            text=text,
            confidence=avg_confidence,
            page_index=page_index,
            provider=self.provider_name,
        )

    def is_available(self) -> bool:
        """Return True when surya-ocr is importable."""
        return _check_surya()

    @property
    def provider_name(self) -> str:
        return "surya"
