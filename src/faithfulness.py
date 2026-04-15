"""
Post-generation faithfulness scorer for the Adaptive RAG Clinical Assistant.

Measures how well a generated response is grounded in the retrieved context
by comparing sentence-level embeddings to context chunk embeddings via cosine
similarity. Uses the embedder already loaded in session state — no additional
model download required.
"""

import re
import time
from dataclasses import dataclass, field

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

FAITHFULNESS_WARNING_THRESHOLD: float = 0.45


@dataclass
class FaithfulnessResult:
    """Holds per-sentence and aggregate faithfulness scores for a response."""

    score: float
    sentence_scores: list[float]
    sentences: list[str]
    low_confidence_sentences: list[str]
    low_confidence_indices: list[int]
    context_chunks_used: int
    latency_ms: float
    sentence_threshold: float = field(default=0.35, repr=False)


class FaithfulnessChecker:
    """Scores how faithfully a response is grounded in the retrieved context.

    Algorithm:
        For each sentence in the response, compute its maximum cosine
        similarity to any retrieved context chunk. The overall score is the
        mean of those per-sentence max-similarities.

    Args:
        embedder: A pre-loaded HuggingFaceEmbeddings (or compatible) instance
            that exposes an ``embed_documents(texts: list[str]) -> list[list[float]]``
            method. Never loaded internally.
        sentence_threshold: Sentences with max-similarity below this value are
            flagged as low-confidence (default 0.35).
        min_sentence_length: Sentences shorter than this character count are
            filtered out before scoring (default 15).
    """

    def __init__(
        self,
        embedder,
        sentence_threshold: float = 0.35,
        min_sentence_length: int = 15,
    ) -> None:
        self._embedder = embedder
        self._sentence_threshold = sentence_threshold
        self._min_sentence_length = min_sentence_length

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, response_text: str, context_documents: list) -> FaithfulnessResult:
        """Score the faithfulness of *response_text* against *context_documents*.

        Args:
            response_text: The LLM-generated response string.
            context_documents: List of LangChain ``Document`` objects returned
                by the retriever. Their ``page_content`` fields are used.

        Returns:
            A :class:`FaithfulnessResult` with aggregate score, per-sentence
            scores, flagged low-confidence sentences, and timing.
        """
        start = time.perf_counter()

        sentences = self._split_sentences(response_text)

        if not sentences or not context_documents:
            elapsed = (time.perf_counter() - start) * 1000
            return FaithfulnessResult(
                score=0.0,
                sentence_scores=[],
                sentences=sentences,
                low_confidence_sentences=[],
                low_confidence_indices=[],
                context_chunks_used=len(context_documents),
                latency_ms=elapsed,
                sentence_threshold=self._sentence_threshold,
            )

        chunk_texts = [doc.page_content for doc in context_documents]

        all_texts = sentences + chunk_texts
        all_embeddings = np.array(self._embedder.embed_documents(all_texts))

        n_sentences = len(sentences)
        sentence_embeddings = all_embeddings[:n_sentences]
        chunk_embeddings = all_embeddings[n_sentences:]

        # Shape: (n_sentences, n_chunks)
        sim_matrix = cosine_similarity(sentence_embeddings, chunk_embeddings)

        per_sentence_scores: list[float] = sim_matrix.max(axis=1).tolist()
        overall_score: float = float(np.mean(per_sentence_scores))

        low_confidence_indices = [
            i for i, s in enumerate(per_sentence_scores) if s < self._sentence_threshold
        ]
        low_confidence_sentences = [sentences[i] for i in low_confidence_indices]

        elapsed = (time.perf_counter() - start) * 1000

        return FaithfulnessResult(
            score=overall_score,
            sentence_scores=per_sentence_scores,
            sentences=sentences,
            low_confidence_sentences=low_confidence_sentences,
            low_confidence_indices=low_confidence_indices,
            context_chunks_used=len(context_documents),
            latency_ms=elapsed,
            sentence_threshold=self._sentence_threshold,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _split_sentences(self, text: str) -> list[str]:
        """Split *text* into sentences and filter by minimum length."""
        if not text or not text.strip():
            return []

        raw = re.split(r"(?<=[.?!])\s+", text.strip())
        return [s.strip() for s in raw if len(s.strip()) >= self._min_sentence_length]
