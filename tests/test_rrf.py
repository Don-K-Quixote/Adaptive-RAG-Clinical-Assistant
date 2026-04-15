"""
Tests for Reciprocal Rank Fusion (RRF) algorithm.

Validates the core RRF implementation against known properties:
- Score formula: score(d) = Σ 1/(k + rank)
- Documents in both lists get summed scores
- Results sorted descending by RRF score
- Rank is 1-indexed
"""

from langchain_core.documents import Document

from src.retrieval import ReciprocalRankFusion


class TestRRFScoreFormula:
    """Verify the fundamental RRF score calculation."""

    def test_single_retriever_score(self):
        """RRF score for rank 1 with k=60 should be 1/61."""
        rrf = ReciprocalRankFusion(k=60)
        doc = Document(page_content="test", metadata={"chunk_id": 0})

        results = rrf.fuse([doc], [], top_n=1)

        assert len(results) == 1
        expected = 1.0 / (60 + 1)  # 1/(k + rank), rank=1
        assert abs(results[0].rrf_score - expected) < 1e-10

    def test_document_in_both_lists_gets_summed_score(self, sample_documents):
        """A document appearing in both lists should have summed RRF scores."""
        rrf = ReciprocalRankFusion(k=60)
        doc = sample_documents[0]

        # Same doc at rank 1 in both lists
        results = rrf.fuse([doc], [doc], top_n=1)

        expected = 1.0 / (60 + 1) + 1.0 / (60 + 1)  # sum of both
        assert abs(results[0].rrf_score - expected) < 1e-10
        assert results[0].found_in_both is True

    def test_rank_2_score_less_than_rank_1(self):
        """Higher rank (lower number) should produce higher score."""
        rrf = ReciprocalRankFusion(k=60)
        doc1 = Document(page_content="first", metadata={"chunk_id": 0})
        doc2 = Document(page_content="second", metadata={"chunk_id": 1})

        results = rrf.fuse([doc1, doc2], [], top_n=2)

        assert results[0].rrf_score > results[1].rrf_score

    def test_custom_k_value(self):
        """RRF with different k values should produce different scores."""
        doc = Document(page_content="test", metadata={"chunk_id": 0})

        rrf_10 = ReciprocalRankFusion(k=10)
        rrf_100 = ReciprocalRankFusion(k=100)

        score_k10 = rrf_10.fuse([doc], [], top_n=1)[0].rrf_score
        score_k100 = rrf_100.fuse([doc], [], top_n=1)[0].rrf_score

        # Lower k -> higher score for same rank
        assert score_k10 > score_k100


class TestRRFFusion:
    """Verify fusion behavior with multiple retrievers."""

    def test_overlapping_results_ranked_higher(self, sample_documents):
        """Documents found by both retrievers should rank above single-retriever docs."""
        rrf = ReciprocalRankFusion(k=60)

        # doc[0] in both, doc[1] only semantic, doc[2] only lexical
        semantic = [sample_documents[0], sample_documents[1]]
        lexical = [sample_documents[0], sample_documents[2]]

        results = rrf.fuse(semantic, lexical, top_n=3)

        # doc[0] should be first (in both)
        assert results[0].document.metadata["chunk_id"] == 0
        assert results[0].found_in_both is True

    def test_disjoint_results(self, sample_documents):
        """Completely disjoint lists should return all documents."""
        rrf = ReciprocalRankFusion(k=60)

        semantic = [sample_documents[0], sample_documents[1]]
        lexical = [sample_documents[2], sample_documents[3]]

        results = rrf.fuse(semantic, lexical, top_n=4)

        assert len(results) == 4
        # No doc should be found_in_both
        assert all(not r.found_in_both for r in results)

    def test_top_n_limits_output(self, sample_documents):
        """Output should be limited to top_n results."""
        rrf = ReciprocalRankFusion(k=60)

        results = rrf.fuse(sample_documents[:3], sample_documents[2:], top_n=2)

        assert len(results) == 2

    def test_empty_inputs(self):
        """Fusing two empty lists should return empty results."""
        rrf = ReciprocalRankFusion(k=60)
        results = rrf.fuse([], [], top_n=5)
        assert len(results) == 0

    def test_one_empty_input(self, sample_documents):
        """Fusing with one empty list should return results from the other."""
        rrf = ReciprocalRankFusion(k=60)
        results = rrf.fuse(sample_documents[:3], [], top_n=3)
        assert len(results) == 3

    def test_results_sorted_descending(self, sample_documents):
        """Results must be sorted by RRF score in descending order."""
        rrf = ReciprocalRankFusion(k=60)
        results = rrf.fuse(sample_documents[:3], sample_documents[1:4], top_n=5)

        scores = [r.rrf_score for r in results]
        assert scores == sorted(scores, reverse=True)


class TestRRFResultMetadata:
    """Verify RRFResult metadata correctness."""

    def test_semantic_only_metadata(self, sample_documents):
        rrf = ReciprocalRankFusion(k=60)
        results = rrf.fuse([sample_documents[0]], [], top_n=1)

        assert results[0].semantic_rank == 1
        assert results[0].lexical_rank is None
        assert results[0].found_in_both is False

    def test_lexical_only_metadata(self, sample_documents):
        rrf = ReciprocalRankFusion(k=60)
        results = rrf.fuse([], [sample_documents[0]], top_n=1)

        assert results[0].semantic_rank is None
        assert results[0].lexical_rank == 1
        assert results[0].found_in_both is False

    def test_both_retriever_metadata(self, sample_documents):
        rrf = ReciprocalRankFusion(k=60)
        results = rrf.fuse([sample_documents[0]], [sample_documents[0]], top_n=1)

        assert results[0].semantic_rank == 1
        assert results[0].lexical_rank == 1
        assert results[0].found_in_both is True


class TestRRFMultipleFusion:
    """Test fuse_multiple for >2 retriever lists."""

    def test_three_retrievers(self, sample_documents):
        rrf = ReciprocalRankFusion(k=60)
        lists = [
            [sample_documents[0], sample_documents[1]],
            [sample_documents[0], sample_documents[2]],
            [sample_documents[0], sample_documents[3]],
        ]

        results = rrf.fuse_multiple(lists, top_n=4)

        # doc[0] is in all 3 lists → highest score
        assert results[0].document.metadata["chunk_id"] == 0
        expected_score = 3 * (1.0 / (60 + 1))
        assert abs(results[0].rrf_score - expected_score) < 1e-10
