"""
Hybrid Retrieval with Reciprocal Rank Fusion (RRF)
===================================================

Implements true Reciprocal Rank Fusion (RRF) for combining semantic and lexical
retrieval results, as described in:

    Cormack, G. V., Clarke, C. L., & Buettcher, S. (2009).
    "Reciprocal rank fusion outperforms condorcet and individual rank learning methods."
    SIGIR '09.

RRF Formula:
    score(d) = Σ 1/(k + rank_i(d))

Where:
    - d is a document
    - rank_i(d) is the rank of d in retriever i (1-indexed)
    - k is a constant (typically 60)

Advantages over Weighted Score Fusion:
    1. Rank-based: Immune to score scale differences between retrievers
    2. No normalization needed: Works regardless of score distributions
    3. Emphasizes top results: Documents ranked highly by multiple retrievers get boosted
    4. Robust: Proven effective across diverse retrieval scenarios
"""

import time
from dataclasses import dataclass
from typing import Any

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from .config import DEFAULT_SCORE_THRESHOLD, DEFAULT_TOP_K, RRF_K_CONSTANT


@dataclass
class RRFResult:
    """Container for RRF retrieval results with metadata."""

    document: Document
    rrf_score: float
    semantic_rank: int | None = None
    lexical_rank: int | None = None

    @property
    def found_in_both(self) -> bool:
        """Check if document was found by both retrievers."""
        return self.semantic_rank is not None and self.lexical_rank is not None


class ReciprocalRankFusion:
    """
    Implements Reciprocal Rank Fusion (RRF) algorithm.

    RRF combines results from multiple retrieval systems using only rank positions,
    making it robust to score scale differences between semantic and lexical retrievers.

    Attributes:
        k: RRF constant (default 60, as recommended in literature)

    Example:
        >>> rrf = ReciprocalRankFusion(k=60)
        >>> fused = rrf.fuse(semantic_results, lexical_results, top_n=5)
    """

    def __init__(self, k: int = RRF_K_CONSTANT):
        """
        Initialize RRF with constant k.

        Args:
            k: The RRF constant. Higher k reduces the impact of rank differences.
               Standard value is 60 (Cormack et al., 2009).
        """
        self.k = k

    def _get_document_id(self, doc: Document) -> str:
        """
        Get unique identifier for a document.

        Uses chunk_id from metadata if available, otherwise falls back to
        content hash for deduplication.
        """
        if "chunk_id" in doc.metadata:
            return f"chunk_{doc.metadata['chunk_id']}"
        # Fallback to content hash
        return str(hash(doc.page_content[:200]))

    def fuse(
        self,
        semantic_results: list[Document],
        lexical_results: list[Document],
        top_n: int = DEFAULT_TOP_K,
    ) -> list[RRFResult]:
        """
        Fuse results from semantic and lexical retrievers using RRF.

        Args:
            semantic_results: Ranked results from semantic/vector retriever
            lexical_results: Ranked results from lexical/BM25 retriever
            top_n: Number of final results to return

        Returns:
            List of RRFResult objects, sorted by RRF score descending

        Algorithm:
            1. For each document in semantic results, compute RRF score: 1/(k + rank)
            2. For each document in lexical results, add RRF score: 1/(k + rank)
            3. Documents appearing in both get their scores summed
            4. Sort by total RRF score and return top_n
        """
        doc_scores: dict[str, dict[str, Any]] = {}

        # Process semantic results (rank starts at 1)
        for rank, doc in enumerate(semantic_results, start=1):
            doc_id = self._get_document_id(doc)
            rrf_score = 1.0 / (self.k + rank)

            doc_scores[doc_id] = {
                "document": doc,
                "rrf_score": rrf_score,
                "semantic_rank": rank,
                "lexical_rank": None,
            }

        # Process lexical results (rank starts at 1)
        for rank, doc in enumerate(lexical_results, start=1):
            doc_id = self._get_document_id(doc)
            rrf_score = 1.0 / (self.k + rank)

            if doc_id in doc_scores:
                # Document appears in both - add scores (key RRF property)
                doc_scores[doc_id]["rrf_score"] += rrf_score
                doc_scores[doc_id]["lexical_rank"] = rank
            else:
                # Document only in lexical results
                doc_scores[doc_id] = {
                    "document": doc,
                    "rrf_score": rrf_score,
                    "semantic_rank": None,
                    "lexical_rank": rank,
                }

        # Sort by RRF score (descending) and create result objects
        sorted_items = sorted(doc_scores.values(), key=lambda x: x["rrf_score"], reverse=True)

        results = [
            RRFResult(
                document=item["document"],
                rrf_score=item["rrf_score"],
                semantic_rank=item["semantic_rank"],
                lexical_rank=item["lexical_rank"],
            )
            for item in sorted_items[:top_n]
        ]

        return results

    def fuse_multiple(
        self, result_lists: list[list[Document]], top_n: int = DEFAULT_TOP_K
    ) -> list[RRFResult]:
        """
        Fuse results from multiple (>2) retrievers using RRF.

        Args:
            result_lists: List of ranked result lists from multiple retrievers
            top_n: Number of final results to return

        Returns:
            List of RRFResult objects, sorted by RRF score descending
        """
        doc_scores: dict[str, dict[str, Any]] = {}

        for _retriever_idx, results in enumerate(result_lists):
            for rank, doc in enumerate(results, start=1):
                doc_id = self._get_document_id(doc)
                rrf_score = 1.0 / (self.k + rank)

                if doc_id in doc_scores:
                    doc_scores[doc_id]["rrf_score"] += rrf_score
                else:
                    doc_scores[doc_id] = {
                        "document": doc,
                        "rrf_score": rrf_score,
                        "semantic_rank": None,
                        "lexical_rank": None,
                    }

        sorted_items = sorted(doc_scores.values(), key=lambda x: x["rrf_score"], reverse=True)

        return [
            RRFResult(document=item["document"], rrf_score=item["rrf_score"])
            for item in sorted_items[:top_n]
        ]


class HybridRetriever:
    """
    Hybrid retriever combining semantic search with BM25 using RRF.

    Provides a unified interface for hybrid retrieval with:
    - Semantic search via vector store (ChromaDB)
    - Lexical search via BM25
    - Fusion via Reciprocal Rank Fusion

    Attributes:
        vectordb: ChromaDB vector store for semantic search
        bm25_retriever: BM25 retriever for lexical search
        rrf: ReciprocalRankFusion instance
        top_k: Number of results to retrieve from each retriever

    Example:
        >>> retriever = HybridRetriever(vectordb, bm25_retriever)
        >>> results = retriever.retrieve("What is RECIST criteria?", top_k=5)
    """

    def __init__(
        self,
        vectordb: Chroma,
        bm25_retriever: BM25Retriever,
        rrf_k: int = RRF_K_CONSTANT,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float | None = DEFAULT_SCORE_THRESHOLD,
    ):
        """
        Initialize hybrid retriever.

        Args:
            vectordb: ChromaDB instance with embedded documents
            bm25_retriever: BM25Retriever instance with indexed documents
            rrf_k: RRF constant (default 60)
            top_k: Default number of results to retrieve
            score_threshold: Minimum RRF score to return a result.
                Documents scoring below this value are filtered out.
                None disables filtering (default). Typical RRF scores for
                top-k=5 from k=10 candidates fall in the range 0.007–0.016.
        """
        self.vectordb = vectordb
        self.bm25_retriever = bm25_retriever
        self.rrf = ReciprocalRankFusion(k=rrf_k)
        self.top_k = top_k
        self.score_threshold = score_threshold

    def retrieve(
        self, query: str, top_k: int | None = None, return_scores: bool = False
    ) -> list[Document]:
        """
        Retrieve documents using hybrid search with RRF fusion.

        Args:
            query: Search query string
            top_k: Number of results to return (default: self.top_k)
            return_scores: If True, returns RRFResult objects instead of Documents

        Returns:
            List of Document objects (or RRFResult if return_scores=True)
        """
        k = top_k or self.top_k

        # Get results from both retrievers
        # Request more candidates than final k for better fusion
        num_candidates = k * 2

        # Semantic retrieval
        semantic_results = self.vectordb.similarity_search(query, k=num_candidates)

        # Lexical retrieval
        self.bm25_retriever.k = num_candidates
        lexical_results = self.bm25_retriever.invoke(query)

        # Fuse with RRF
        fused_results = self.rrf.fuse(semantic_results, lexical_results, top_n=k)

        # Apply minimum-score gate to filter low-quality matches
        if self.score_threshold is not None:
            fused_results = [r for r in fused_results if r.rrf_score >= self.score_threshold]

        if return_scores:
            return fused_results

        return [result.document for result in fused_results]

    def retrieve_with_metadata(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        """
        Retrieve documents with detailed metadata about the retrieval process.

        Args:
            query: Search query string
            top_k: Number of results to return

        Returns:
            Dictionary containing:
                - documents: List of retrieved documents
                - rrf_results: List of RRFResult with scores
                - timing: Timing information
                - stats: Retrieval statistics
        """
        k = top_k or self.top_k
        num_candidates = k * 2

        # Semantic retrieval with timing
        start_semantic = time.time()
        semantic_results = self.vectordb.similarity_search(query, k=num_candidates)
        semantic_time = (time.time() - start_semantic) * 1000

        # Lexical retrieval with timing
        start_lexical = time.time()
        self.bm25_retriever.k = num_candidates
        lexical_results = self.bm25_retriever.invoke(query)
        lexical_time = (time.time() - start_lexical) * 1000

        # Fusion with timing
        start_fusion = time.time()
        fused_results = self.rrf.fuse(semantic_results, lexical_results, top_n=k)

        # Apply minimum-score gate to filter low-quality matches
        if self.score_threshold is not None:
            fused_results = [r for r in fused_results if r.rrf_score >= self.score_threshold]

        fusion_time = (time.time() - start_fusion) * 1000

        # Calculate statistics
        in_both = sum(1 for r in fused_results if r.found_in_both)
        semantic_only = sum(1 for r in fused_results if r.semantic_rank and not r.lexical_rank)
        lexical_only = sum(1 for r in fused_results if r.lexical_rank and not r.semantic_rank)

        return {
            "documents": [r.document for r in fused_results],
            "rrf_results": fused_results,
            "timing": {
                "semantic_ms": round(semantic_time, 2),
                "lexical_ms": round(lexical_time, 2),
                "fusion_ms": round(fusion_time, 2),
                "total_ms": round(semantic_time + lexical_time + fusion_time, 2),
            },
            "stats": {
                "candidates_semantic": len(semantic_results),
                "candidates_lexical": len(lexical_results),
                "final_count": len(fused_results),
                "found_in_both": in_both,
                "semantic_only": semantic_only,
                "lexical_only": lexical_only,
                "score_threshold": self.score_threshold,
            },
        }

    def semantic_only(self, query: str, top_k: int | None = None) -> list[Document]:
        """Retrieve using only semantic search (for comparison)."""
        k = top_k or self.top_k
        return self.vectordb.similarity_search(query, k=k)

    def lexical_only(self, query: str, top_k: int | None = None) -> list[Document]:
        """Retrieve using only BM25 lexical search (for comparison)."""
        k = top_k or self.top_k
        self.bm25_retriever.k = k
        return self.bm25_retriever.invoke(query)
