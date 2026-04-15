"""
Smart PDF ingestion with auto-detect OCR routing.

Each page is classified independently:
- Text-native pages (long text layer, no images) → fast pdfplumber extraction.
- Image-heavy / scanned pages → routed to an OCRProvider (Surya or OpenAI Vision).

The result is a list of LangChain Documents ready for chunking and indexing.

Detection heuristic
-------------------
A page is "NEEDS_OCR" when **both** conditions are true:
    1. Extracted text length < OCR_TEXT_THRESHOLD characters.
    2. The page contains at least one embedded image.

This avoids running OCR on pages that simply have no text (e.g. blank pages)
as well as pages that already have a usable text layer.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from pathlib import Path

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ocr.base import OCRProvider

logger = logging.getLogger(__name__)

# A page is considered "image-heavy / scanned" if its extracted text is shorter
# than this threshold AND it contains at least one embedded image.
OCR_TEXT_THRESHOLD = 50

# DPI used when rasterising a PDF page to a PIL Image for OCR.
RASTER_DPI = 200


class PageClassification(Enum):
    TEXT_NATIVE = "text_native"
    NEEDS_OCR = "needs_ocr"


def _classify_page(page: pdfplumber.page.Page) -> PageClassification:
    """Decide whether a page needs OCR.

    Args:
        page: An open pdfplumber Page object.

    Returns:
        TEXT_NATIVE if the page has sufficient extractable text,
        NEEDS_OCR if the page is image-heavy or a scan.
    """
    text = page.extract_text() or ""
    has_images = bool(page.images)

    if len(text.strip()) < OCR_TEXT_THRESHOLD and has_images:
        return PageClassification.NEEDS_OCR

    return PageClassification.TEXT_NATIVE


def _page_to_pil(pdf_path: Path, page_number: int):
    """Rasterise a single PDF page to a PIL Image.

    Args:
        pdf_path: Absolute path to the PDF file.
        page_number: 1-based page number.

    Returns:
        PIL.Image.Image of the rendered page.
    """
    from pdf2image import convert_from_path

    images = convert_from_path(
        str(pdf_path),
        first_page=page_number,
        last_page=page_number,
        dpi=RASTER_DPI,
    )
    return images[0]


class DocumentIngester:
    """Ingest a PDF into LangChain Documents using smart page routing.

    Text-native pages are extracted with pdfplumber (fast, free).
    Scanned/image-heavy pages are passed to the configured OCRProvider.

    Args:
        ocr_provider: An OCRProvider instance, or None to disable OCR.
            When None, NEEDS_OCR pages are logged as warnings and skipped.
        chunk_size: Target token size for each text chunk.
        chunk_overlap: Overlap between consecutive chunks.
        progress_callback: Optional callable(page_index, total_pages, classification)
            called after each page is processed — useful for Streamlit progress bars.
    """

    def __init__(
        self,
        ocr_provider: OCRProvider | None,
        chunk_size: int = 800,
        chunk_overlap: int = 150,
        progress_callback: Callable[[int, int, PageClassification], None] | None = None,
    ) -> None:
        self.ocr_provider = ocr_provider
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.progress_callback = progress_callback

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
        )

    def ingest(self, pdf_path: Path) -> list[Document]:
        """Extract, classify, and chunk all pages from a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            List of LangChain Documents with metadata including page index,
            classification, and OCR provider (if applicable).

        Raises:
            FileNotFoundError: If the PDF path does not exist.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        raw_pages: list[Document] = []
        stats = {"text_native": 0, "needs_ocr": 0, "skipped": 0}

        with pdfplumber.open(pdf_path) as pdf:
            total = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                classification = _classify_page(page)

                if classification == PageClassification.TEXT_NATIVE:
                    text = page.extract_text() or ""
                    ocr_provider_name = "none"
                    stats["text_native"] += 1

                else:  # NEEDS_OCR
                    if self.ocr_provider is None or not self.ocr_provider.is_available():
                        logger.warning(
                            f"Page {i} needs OCR but no provider is available — skipping."
                        )
                        stats["skipped"] += 1
                        if self.progress_callback:
                            self.progress_callback(i, total, classification)
                        continue

                    try:
                        pil_image = _page_to_pil(pdf_path, page_number=i + 1)
                        ocr_result = self.ocr_provider.ocr_image(pil_image, page_index=i)
                        text = ocr_result.text
                        ocr_provider_name = ocr_result.provider
                        stats["needs_ocr"] += 1
                    except Exception:
                        logger.exception(f"OCR failed on page {i} — skipping.")
                        stats["skipped"] += 1
                        if self.progress_callback:
                            self.progress_callback(i, total, classification)
                        continue

                if text.strip():
                    raw_pages.append(
                        Document(
                            page_content=text,
                            metadata={
                                "page": i,
                                "doc_name": pdf_path.name,
                                "classification": classification.value,
                                "ocr_provider": ocr_provider_name,
                            },
                        )
                    )

                if self.progress_callback:
                    self.progress_callback(i, total, classification)

        logger.info(
            f"Ingestion complete — "
            f"{stats['text_native']} text-native, "
            f"{stats['needs_ocr']} OCR'd, "
            f"{stats['skipped']} skipped."
        )

        chunks = self._splitter.split_documents(raw_pages)

        # Stamp chunk_id after splitting so IDs are contiguous and unique
        for chunk_id, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = chunk_id

        return chunks

    @property
    def last_stats(self) -> dict:
        """Return ingestion statistics from the most recent ingest() call.

        Provided as a convenience so callers (e.g. Streamlit) can display
        a summary without parsing log output.
        """
        # Stats are re-computed per call inside ingest(); expose via return value
        # in practice.  This property is a stub kept for API compatibility.
        return {}
