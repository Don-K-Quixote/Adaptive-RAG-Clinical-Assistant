"""
Tests for DocumentIngester.

All external I/O (pdfplumber, pdf2image, OCR providers) is mocked so that
tests run offline without real PDFs or model calls.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from src.ingestion import DocumentIngester, PageClassification, _classify_page
from src.ocr.base import OCRResult

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_page(text: str = "", images: list | None = None):
    """Return a mock pdfplumber Page with controllable text and images."""
    page = MagicMock()
    page.extract_text.return_value = text
    page.images = images if images is not None else []
    return page


def _make_mock_ocr_provider(text: str = "OCR extracted text", confidence: float = 0.9):
    """Return a mock OCRProvider that returns a fixed OCRResult."""
    provider = MagicMock()
    provider.is_available.return_value = True
    provider.provider_name = "mock_ocr"
    provider.ocr_image.return_value = OCRResult(
        text=text,
        confidence=confidence,
        page_index=0,
        provider="mock_ocr",
    )
    return provider


# ---------------------------------------------------------------------------
# _classify_page unit tests
# ---------------------------------------------------------------------------


def test_classify_page_text_native():
    """A page with plenty of text should be classified as TEXT_NATIVE."""
    page = _make_mock_page(text="A" * 200)
    assert _classify_page(page) == PageClassification.TEXT_NATIVE


def test_classify_page_needs_ocr_short_text_with_image():
    """A page with short text AND at least one image should require OCR."""
    page = _make_mock_page(text="hi", images=[{"object_type": "image"}])
    assert _classify_page(page) == PageClassification.NEEDS_OCR


def test_classify_page_text_native_despite_image_if_enough_text():
    """Even with an image, a page with long text is TEXT_NATIVE (no need for OCR)."""
    page = _make_mock_page(text="B" * 200, images=[{"object_type": "image"}])
    assert _classify_page(page) == PageClassification.TEXT_NATIVE


def test_classify_page_text_native_no_image_short_text():
    """A page with short text but NO images stays TEXT_NATIVE (blank page, no scan)."""
    page = _make_mock_page(text="tiny", images=[])
    assert _classify_page(page) == PageClassification.TEXT_NATIVE


# ---------------------------------------------------------------------------
# DocumentIngester integration-level tests (PDF mocked)
# ---------------------------------------------------------------------------


def _patch_pdfplumber(pages: list, monkeypatch=None):
    """Return a context manager that replaces pdfplumber.open with a stub."""
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = pages
    return patch("src.ingestion.pdfplumber.open", return_value=mock_pdf)


def test_ingest_text_pdf_no_ocr(tmp_path):
    """Ingesting a text-only PDF (no OCR provider) should return Documents."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    pages = [_make_mock_page(text="A" * 200), _make_mock_page(text="B" * 200)]

    ingester = DocumentIngester(ocr_provider=None, chunk_size=800, chunk_overlap=50)

    with _patch_pdfplumber(pages):
        docs = ingester.ingest(pdf_file)

    assert len(docs) > 0
    for doc in docs:
        assert isinstance(doc, Document)
        assert "page" in doc.metadata
        assert "chunk_id" in doc.metadata


def test_ingest_calls_ocr_on_image_page(tmp_path):
    """When a page needs OCR, the provider's ocr_image() should be called."""
    pdf_file = tmp_path / "scan.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    image_page = _make_mock_page(text="", images=[{"object_type": "image"}])
    mock_provider = _make_mock_ocr_provider(text="Extracted from scan")

    ingester = DocumentIngester(ocr_provider=mock_provider, chunk_size=800, chunk_overlap=50)

    with _patch_pdfplumber([image_page]):
        with patch("src.ingestion._page_to_pil", return_value=MagicMock()):
            docs = ingester.ingest(pdf_file)

    mock_provider.ocr_image.assert_called_once()
    assert any("Extracted from scan" in d.page_content for d in docs)


def test_ingest_skips_page_if_no_provider(tmp_path, caplog):
    """NEEDS_OCR pages with provider=None should be skipped with a warning."""
    import logging

    pdf_file = tmp_path / "scan.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    image_page = _make_mock_page(text="", images=[{"object_type": "image"}])

    ingester = DocumentIngester(ocr_provider=None, chunk_size=800, chunk_overlap=50)

    with caplog.at_level(logging.WARNING, logger="src.ingestion"):
        with _patch_pdfplumber([image_page]):
            docs = ingester.ingest(pdf_file)

    assert docs == []
    assert any("no provider" in record.message.lower() for record in caplog.records)


def test_ingest_raises_on_missing_pdf():
    """ingest() should raise FileNotFoundError for a non-existent path."""
    ingester = DocumentIngester(ocr_provider=None)
    with pytest.raises(FileNotFoundError):
        ingester.ingest(Path("/nonexistent/path/file.pdf"))


def test_ingest_ocr_metadata_set(tmp_path):
    """OCR'd pages should have ocr_provider set to the provider's name."""
    pdf_file = tmp_path / "scan.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    image_page = _make_mock_page(text="", images=[{"object_type": "image"}])
    mock_provider = _make_mock_ocr_provider(text="OCR text here")

    ingester = DocumentIngester(ocr_provider=mock_provider, chunk_size=800, chunk_overlap=50)

    with _patch_pdfplumber([image_page]):
        with patch("src.ingestion._page_to_pil", return_value=MagicMock()):
            docs = ingester.ingest(pdf_file)

    assert all(d.metadata["ocr_provider"] == "mock_ocr" for d in docs)
    assert all(d.metadata["classification"] == PageClassification.NEEDS_OCR.value for d in docs)
