"""
Tests for query type classification.

Validates pattern-matching classification of user queries into 9 categories.
"""

import pytest

from src.query_classifier import QueryClassifier, QueryType, classify_query


class TestQueryClassification:
    """Core classification tests for each query type."""

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("What is RECIST 1.1?", QueryType.DEFINITION),
            ("Define complete response", QueryType.DEFINITION),
            ("Explain the imaging protocol", QueryType.DEFINITION),
            ("What does partial response mean?", QueryType.DEFINITION),
        ],
    )
    def test_definition_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("How to perform tumor measurements?", QueryType.PROCEDURE),
            ("Steps for image assessment", QueryType.PROCEDURE),
            ("What is the process for adjudication?", QueryType.PROCEDURE),
            ("Workflow for handling discrepancies", QueryType.PROCEDURE),
        ],
    )
    def test_procedure_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("What are the FDA requirements?", QueryType.COMPLIANCE),
            ("ICH-GCP guidelines for imaging", QueryType.COMPLIANCE),
            ("21 CFR Part 11 compliance", QueryType.COMPLIANCE),
            ("Regulatory inspection readiness", QueryType.COMPLIANCE),
        ],
    )
    def test_compliance_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("Compare RECIST vs RANO criteria", QueryType.COMPARISON),
            ("Difference between CR and PR", QueryType.COMPARISON),
            ("What is the difference between central and local review?", QueryType.COMPARISON),
        ],
    )
    def test_comparison_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("How many imaging timepoints are there?", QueryType.NUMERICAL),
            ("What percentage of patients had CR?", QueryType.NUMERICAL),
            ("Total number of reviewers", QueryType.NUMERICAL),
        ],
    )
    def test_numerical_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("When is the baseline scan performed?", QueryType.TIMELINE),
            ("What is the imaging schedule?", QueryType.TIMELINE),
            ("How long between assessments?", QueryType.TIMELINE),
        ],
    )
    def test_timeline_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("What are the safety monitoring procedures?", QueryType.SAFETY),
            ("How are adverse events reported?", QueryType.SAFETY),
            ("List the SAE reporting requirements", QueryType.SAFETY),
            ("What are the known risks?", QueryType.SAFETY),
        ],
    )
    def test_safety_queries(self, query, expected):
        assert classify_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("What are the inclusion criteria?", QueryType.ELIGIBILITY),
            ("List exclusion criteria for enrollment", QueryType.ELIGIBILITY),
            ("Who is eligible for the study?", QueryType.ELIGIBILITY),
        ],
    )
    def test_eligibility_queries(self, query, expected):
        assert classify_query(query) == expected


class TestComplexAndDefault:
    """Test complex query detection and default fallback."""

    def test_multi_question_classified_as_complex(self):
        query = "What is RECIST? How does it compare to RANO? When should each be used?"
        assert classify_query(query) == QueryType.COMPLEX

    def test_unrecognized_query_defaults_to_definition(self):
        """Queries matching no pattern should fall back to DEFINITION."""
        query = "Tell me about the charter"
        assert classify_query(query) == QueryType.DEFINITION


class TestCaseInsensitivity:
    """Ensure classification is case-insensitive."""

    def test_uppercase(self):
        assert classify_query("WHAT IS RECIST?") == QueryType.DEFINITION

    def test_mixed_case(self):
        assert classify_query("How To Measure Tumors") == QueryType.PROCEDURE


class TestConfidence:
    """Test confidence scoring."""

    def test_high_confidence_with_multiple_matches(self):
        """Query with multiple pattern matches should have higher confidence."""
        query = "Define and explain the meaning of complete response"
        query_type = classify_query(query)
        confidence = QueryClassifier.get_confidence(query, query_type)
        assert confidence > 0.5

    def test_complex_default_confidence(self):
        """COMPLEX type should return default confidence."""
        confidence = QueryClassifier.get_confidence("A? B? C?", QueryType.COMPLEX)
        assert confidence == 0.5
