"""Tests for src/utils.py utility functions."""

from langchain_core.documents import Document

from src.utils import format_source_reference


class TestFormatSourceReference:
    def _doc(self, **metadata) -> Document:
        return Document(page_content="text", metadata=metadata)

    def test_happy_path(self):
        doc = self._doc(page=3, chunk_id=7)
        assert format_source_reference(doc, index=1) == "[Source 1: Page 3, Chunk 7]"

    def test_default_index_is_1(self):
        doc = self._doc(page=1, chunk_id=0)
        assert format_source_reference(doc) == "[Source 1: Page 1, Chunk 0]"

    def test_missing_page_returns_na(self):
        doc = self._doc(chunk_id=5)  # no page key
        result = format_source_reference(doc, index=2)
        assert "N/A" in result
        assert "Chunk 5" in result

    def test_missing_chunk_id_returns_na(self):
        doc = self._doc(page=4)  # no chunk_id key
        result = format_source_reference(doc, index=1)
        assert "Page 4" in result
        assert "N/A" in result

    def test_both_missing_returns_na_na(self):
        doc = self._doc()  # empty metadata
        result = format_source_reference(doc, index=1)
        assert result == "[Source 1: Page N/A, Chunk N/A]"

    def test_custom_index(self):
        doc = self._doc(page=10, chunk_id=99)
        assert format_source_reference(doc, index=5) == "[Source 5: Page 10, Chunk 99]"
