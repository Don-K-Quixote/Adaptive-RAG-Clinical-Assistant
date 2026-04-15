"""
Tests for OCRFactory.

All tests avoid triggering real model loads or API calls; they verify
only instantiation behaviour and availability checks.
"""

import pytest

from src.ocr.factory import OCRFactory
from src.ocr.openai_provider import OpenAIVisionProvider
from src.ocr.surya_provider import SuryaProvider


def test_factory_creates_surya():
    """OCRFactory should return a SuryaProvider without loading models."""
    provider = OCRFactory.create("surya")
    assert isinstance(provider, SuryaProvider)
    assert provider.provider_name == "surya"


def test_factory_creates_openai():
    """OCRFactory should return an OpenAIVisionProvider with the given API key."""
    provider = OCRFactory.create("openai", model="gpt-4o-mini", api_key="sk-dummy-key")
    assert isinstance(provider, OpenAIVisionProvider)
    assert provider.provider_name == "openai"
    assert provider.model == "gpt-4o-mini"
    assert provider.api_key == "sk-dummy-key"


def test_factory_invalid_provider_raises():
    """OCRFactory should raise ValueError for unrecognised provider names."""
    with pytest.raises(ValueError, match="Unknown OCR provider"):
        OCRFactory.create("unknown_provider")


def test_openai_provider_is_available_when_key_set():
    """OpenAIVisionProvider.is_available() returns True when an API key is provided."""
    provider = OpenAIVisionProvider(model="gpt-4o", api_key="sk-test")
    assert provider.is_available() is True


def test_openai_provider_not_available_without_key(monkeypatch):
    """OpenAIVisionProvider.is_available() returns False when no API key is set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIVisionProvider(model="gpt-4o", api_key="")
    assert provider.is_available() is False


def test_surya_provider_name():
    provider = SuryaProvider()
    assert provider.provider_name == "surya"


def test_openai_provider_name():
    provider = OpenAIVisionProvider(api_key="sk-test")
    assert provider.provider_name == "openai"
