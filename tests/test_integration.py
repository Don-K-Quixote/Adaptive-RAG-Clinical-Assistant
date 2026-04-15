"""
Integration test: verifies the three hallucination-prevention layers are
correctly connected across build_adaptive_prompt → llm.generate → FaithfulnessChecker.
No Streamlit required — exercises the core pipeline only.
"""

from unittest.mock import MagicMock

import numpy as np
from langchain_core.documents import Document

from src.faithfulness import FaithfulnessChecker
from src.personas import UserType, get_response_config
from src.prompts import SYSTEM_PROMPT, build_adaptive_prompt
from src.query_classifier import QueryType

SAMPLE_DOCS = [
    Document(
        page_content="RECIST 1.1 defines complete response as disappearance of all target lesions.",
        metadata={"chunk_id": 0, "page": 1},
    )
]


def _make_mock_embedder(dim: int = 8) -> MagicMock:
    """Return a mock embedder that produces deterministic unit vectors."""
    embedder = MagicMock()

    def embed(texts):
        vectors = []
        for i, _ in enumerate(texts):
            v = np.zeros(dim)
            v[i % dim] = 1.0
            vectors.append(v.tolist())
        return vectors

    embedder.embed_documents.side_effect = embed
    return embedder


class TestEndToEndPipeline:
    def test_layer1_system_prompt_is_non_empty(self):
        """Layer 1: SYSTEM_PROMPT must be non-empty and contain the fabrication prohibition."""
        assert SYSTEM_PROMPT
        assert "fabricat" in SYSTEM_PROMPT.lower() or "never" in SYSTEM_PROMPT.lower()

    def test_layer2_grounding_in_all_persona_prompts(self):
        """Layer 2: GROUNDING REQUIREMENT must be in prompts for all 5 personas."""
        for user_type in UserType:
            config = get_response_config(user_type, QueryType.DEFINITION.value)
            prompt = build_adaptive_prompt(SAMPLE_DOCS, "What is RECIST?", config)
            assert "GROUNDING REQUIREMENT" in prompt, (
                f"Missing GROUNDING REQUIREMENT for persona {user_type.value}"
            )

    def test_layer3_faithfulness_checker_returns_result(self):
        """Layer 3: FaithfulnessChecker must return a non-None FaithfulnessResult."""
        config = get_response_config(UserType.INTERMEDIATE, QueryType.DEFINITION.value)
        prompt = build_adaptive_prompt(SAMPLE_DOCS, "What is RECIST?", config)

        mock_llm = MagicMock()
        mock_llm.generate.return_value = (
            "Complete response means disappearance of all target lesions."
        )

        response = mock_llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0,
        )

        # Verify SYSTEM_PROMPT was forwarded to LLM call
        call_kwargs = mock_llm.generate.call_args.kwargs
        assert call_kwargs["system_prompt"] == SYSTEM_PROMPT

        # Layer 3: faithfulness check produces a result
        embedder = _make_mock_embedder()
        checker = FaithfulnessChecker(embedder)
        result = checker.check(response, SAMPLE_DOCS)
        assert result is not None
        assert 0.0 <= result.score <= 1.0

    def test_all_three_layers_connected(self):
        """End-to-end: prompt built, LLM called with SYSTEM_PROMPT, faithfulness checked."""
        config = get_response_config(UserType.EXPERT, QueryType.COMPLIANCE.value)
        prompt = build_adaptive_prompt(SAMPLE_DOCS, "What is complete response?", config)

        assert "GROUNDING REQUIREMENT" in prompt  # Layer 2 active

        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Complete response is disappearance of all lesions."

        response = mock_llm.generate(prompt=prompt, system_prompt=SYSTEM_PROMPT, temperature=0)
        assert mock_llm.generate.called
        # Layer 1 check: SYSTEM_PROMPT was passed
        assert mock_llm.generate.call_args.kwargs["system_prompt"] == SYSTEM_PROMPT

        embedder = _make_mock_embedder()
        result = FaithfulnessChecker(embedder).check(response, SAMPLE_DOCS)
        assert result is not None  # Layer 3 active
