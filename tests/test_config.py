"""
Tests for configuration validation.

Ensures config.py constants are consistent and complete.
"""


from src.config import (
    DEFAULT_BM25_WEIGHT,
    DEFAULT_LLM_MODEL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_SEMANTIC_WEIGHT,
    DEFAULT_TOP_K,
    EMBEDDING_MODELS,
    LLM_PROVIDERS,
    OLLAMA_MODELS,
    OPENAI_MODELS,
    RRF_K_CONSTANT,
)


class TestEmbeddingModels:
    """Validate embedding model configuration completeness."""

    def test_all_models_have_required_keys(self):
        required_keys = {"name", "type", "description", "dimensions", "max_seq_length"}
        for key, config in EMBEDDING_MODELS.items():
            missing = required_keys - set(config.keys())
            assert not missing, f"Model '{key}' missing keys: {missing}"

    def test_spubmedbert_is_registered(self):
        """Primary medical model must be present."""
        assert "S-PubMedBert-MS-MARCO" in EMBEDDING_MODELS

    def test_medical_models_have_correct_type(self):
        medical_models = ["S-PubMedBert-MS-MARCO", "BioSimCSE-BioLinkBERT", "BioBERT"]
        for model in medical_models:
            assert EMBEDDING_MODELS[model]["type"] == "medical"


class TestLLMModels:
    """Validate LLM model configurations."""

    def test_default_openai_model_exists(self):
        assert DEFAULT_LLM_MODEL in OPENAI_MODELS

    def test_default_local_model_exists(self):
        assert DEFAULT_LOCAL_MODEL in OLLAMA_MODELS

    def test_medgemma_in_ollama(self):
        assert "alibayram/medgemma:4b" in OLLAMA_MODELS

    def test_ollama_models_have_vram(self):
        for key, config in OLLAMA_MODELS.items():
            assert "vram_required" in config, f"'{key}' missing vram_required"

    def test_all_models_have_context_window(self):
        for key, config in OPENAI_MODELS.items():
            assert "context_window" in config, f"OpenAI '{key}' missing context_window"
        for key, config in OLLAMA_MODELS.items():
            assert "context_window" in config, f"Ollama '{key}' missing context_window"


class TestRetrievalDefaults:
    """Validate retrieval configuration constants."""

    def test_rrf_k_is_60(self):
        """Standard RRF k=60 per Cormack et al., 2009."""
        assert RRF_K_CONSTANT == 60

    def test_weights_sum_to_one(self):
        assert abs(DEFAULT_SEMANTIC_WEIGHT + DEFAULT_BM25_WEIGHT - 1.0) < 1e-10

    def test_top_k_positive(self):
        assert DEFAULT_TOP_K > 0

    def test_provider_options(self):
        assert "OpenAI (Cloud)" in LLM_PROVIDERS
        assert "Ollama (Local)" in LLM_PROVIDERS
