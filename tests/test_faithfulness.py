"""
Tests for the FaithfulnessChecker post-generation scorer.

Uses deterministic numpy vectors via unittest.mock.MagicMock so tests never
make real network calls. Follows the class-based structure from test_prompts.py.
"""

from unittest.mock import MagicMock

import numpy as np
import pytest
from langchain_core.documents import Document

from src.faithfulness import FAITHFULNESS_WARNING_THRESHOLD, FaithfulnessChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedder(vectors: list[list[float]]) -> MagicMock:
    """Return a mock embedder whose embed_documents returns *vectors* in order."""
    embedder = MagicMock()
    embedder.embed_documents.return_value = [list(v) for v in vectors]
    return embedder


def _unit(n: int, dim: int = 4) -> np.ndarray:
    """Return a unit vector with a 1.0 at index *n* and zeros elsewhere."""
    v = np.zeros(dim)
    v[n] = 1.0
    return v


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_documents():
    """Three context chunks — used for structural tests."""
    return [
        Document(page_content="RECIST 1.1 defines complete response.", metadata={}),
        Document(page_content="Baseline CT required within 28 days.", metadata={}),
        Document(page_content="Partial response is a 30 percent decrease.", metadata={}),
    ]


# ---------------------------------------------------------------------------
# TestFaithfulnessCheckerScores
# ---------------------------------------------------------------------------


class TestFaithfulnessCheckerScores:
    """Core scoring behaviour of FaithfulnessChecker."""

    def test_perfect_score_when_response_matches_context(self, sample_documents):
        """Score should be 1.0 when each response sentence vector equals a context vector."""
        # Order: sentences first, then chunks (as passed to embed_documents)
        # 3 sentences + 3 chunks, aligned unit vectors → cosine sim = 1.0
        vectors = [_unit(0), _unit(1), _unit(2), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder)

        response = (
            "Complete response means all lesions disappear. "
            "Baseline imaging is required before randomization. "
            "Partial response requires a thirty percent shrinkage."
        )
        result = checker.check(response, sample_documents)

        assert abs(result.score - 1.0) < 1e-6

    def test_zero_score_when_vectors_orthogonal(self, sample_documents):
        """Score should be 0.0 when the sentence vector is orthogonal to every chunk vector."""
        # 1 sentence (dim 3) + 3 chunks (dims 0,1,2) — all orthogonal
        vectors = [_unit(3), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check(
            "This sentence is completely unrelated to the context.", sample_documents
        )

        assert abs(result.score - 0.0) < 1e-6

    def test_partial_score_for_mixed_response(self, sample_documents):
        """Score should be the mean of per-sentence max-similarities."""
        # sentence 0: dim 0 matches chunk 0 → max-sim 1.0
        # sentence 1: dim 3 matches nothing → max-sim 0.0
        # expected mean = 0.5
        vectors = [
            _unit(0),  # sentence 0
            _unit(3),  # sentence 1
            _unit(0),  # chunk 0
            _unit(1),  # chunk 1
            _unit(2),  # chunk 2
        ]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check(
            "Complete response means all lesions disappear. This claim has no support at all.",
            sample_documents,
        )

        assert abs(result.score - 0.5) < 1e-6
        assert len(result.sentence_scores) == 2

    def test_sentence_scores_length_matches_sentences(self, sample_documents):
        """sentence_scores length must equal sentences length."""
        vectors = [_unit(0), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check(
            "One sentence here is fine. Another sentence follows.", sample_documents
        )

        assert len(result.sentence_scores) == len(result.sentences)


# ---------------------------------------------------------------------------
# TestLowConfidenceFlagging
# ---------------------------------------------------------------------------


class TestLowConfidenceFlagging:
    """Sentences below sentence_threshold should be flagged as low-confidence."""

    def test_low_confidence_sentences_flagged(self, sample_documents):
        """Sentences with max-similarity below threshold appear in low_confidence_sentences."""
        # sentence 0 → sim 1.0 (above threshold)
        # sentence 1 → sim 0.0 (below threshold 0.35)
        vectors = [
            _unit(0),  # sentence 0
            _unit(3),  # sentence 1
            _unit(0),  # chunk 0
            _unit(1),  # chunk 1
            _unit(2),  # chunk 2
        ]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder, sentence_threshold=0.35)

        result = checker.check(
            "Complete response means all lesions disappear. This claim has no support at all.",
            sample_documents,
        )

        assert len(result.low_confidence_sentences) == 1
        assert result.low_confidence_indices == [1]

    def test_no_low_confidence_when_all_above_threshold(self, sample_documents):
        """No sentences should be flagged when all similarities exceed the threshold."""
        vectors = [_unit(0), _unit(1), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder, sentence_threshold=0.35)

        result = checker.check(
            "Complete response means disappearance. Baseline imaging is required.",
            sample_documents,
        )

        assert result.low_confidence_sentences == []
        assert result.low_confidence_indices == []


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Empty inputs, short sentences, and sentinel behaviour."""

    def test_empty_response_returns_zero_score(self, sample_documents):
        """An empty response string should return score 0.0 without crashing."""
        embedder = MagicMock()
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check("", sample_documents)

        assert result.score == 0.0
        assert result.sentences == []
        embedder.embed_documents.assert_not_called()

    def test_empty_documents_returns_zero_score(self):
        """No context documents should return score 0.0 without crashing."""
        embedder = MagicMock()
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check("This is a response sentence long enough to pass filter.", [])

        assert result.score == 0.0
        assert result.context_chunks_used == 0
        embedder.embed_documents.assert_not_called()

    def test_short_sentences_filtered(self, sample_documents):
        """Sentences shorter than min_sentence_length characters should be excluded."""
        vectors = [_unit(0), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder, min_sentence_length=15)

        # "Short." is only 6 chars — below threshold of 15
        result = checker.check(
            "Short. This is a longer sentence that passes the filter.", sample_documents
        )

        assert len(result.sentences) == 1
        assert "longer sentence" in result.sentences[0]

    def test_whitespace_only_response_returns_zero_score(self, sample_documents):
        """Whitespace-only response should be treated the same as empty."""
        embedder = MagicMock()
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check("   \n\t  ", sample_documents)

        assert result.score == 0.0
        embedder.embed_documents.assert_not_called()


# ---------------------------------------------------------------------------
# TestResultMetadata
# ---------------------------------------------------------------------------


class TestResultMetadata:
    """Verify FaithfulnessResult fields are populated correctly."""

    def test_latency_ms_non_negative(self, sample_documents):
        """latency_ms must always be >= 0."""
        vectors = [_unit(0), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check(
            "This is a well-grounded sentence from the context.", sample_documents
        )

        assert result.latency_ms >= 0.0

    def test_context_chunks_used_equals_doc_count(self, sample_documents):
        """context_chunks_used should equal the number of documents passed in."""
        vectors = [_unit(0), _unit(0), _unit(1), _unit(2)]
        embedder = _make_embedder(vectors)
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check(
            "This is a well-grounded sentence from the context.", sample_documents
        )

        assert result.context_chunks_used == len(sample_documents)

    def test_context_chunks_used_zero_for_empty_docs(self):
        """context_chunks_used should be 0 when no documents are provided."""
        embedder = MagicMock()
        checker = FaithfulnessChecker(embedder=embedder)

        result = checker.check("This response has no supporting context at all.", [])

        assert result.context_chunks_used == 0


# ---------------------------------------------------------------------------
# TestConstant
# ---------------------------------------------------------------------------


class TestConstant:
    """Validate the module-level warning threshold constant."""

    def test_faithfulness_warning_threshold_in_valid_range(self):
        """FAITHFULNESS_WARNING_THRESHOLD must be between 0.0 and 1.0 exclusive."""
        assert 0.0 < FAITHFULNESS_WARNING_THRESHOLD < 1.0

    def test_faithfulness_warning_threshold_value(self):
        """Exact value should be 0.45 as specified in the plan."""
        assert FAITHFULNESS_WARNING_THRESHOLD == 0.45

    def test_threshold_comparison_triggers_warning(self):
        """Score just below threshold → condition evaluates True (warning triggered)."""
        score = 0.44
        assert score < FAITHFULNESS_WARNING_THRESHOLD

    def test_threshold_comparison_does_not_trigger_warning(self):
        """Score at or above threshold → condition evaluates False (no warning)."""
        score = 0.46
        assert not (score < FAITHFULNESS_WARNING_THRESHOLD)
