"""
Query Type Classification
=========================

Classifies user queries into semantic categories for adaptive response formatting.

Query Types:
- DEFINITION: "What is...", "Define...", "Explain..."
- PROCEDURE: "How to...", "Steps for...", "Process of..."
- COMPLIANCE: Regulatory questions (FDA, ICH-GCP, etc.)
- COMPARISON: "Compare...", "Difference between..."
- NUMERICAL: "How many...", "Count of...", "Percentage..."
- TIMELINE: "When...", "Schedule...", "Duration..."
- SAFETY: Adverse events, risks, safety considerations
- ELIGIBILITY: Inclusion/exclusion criteria
- COMPLEX: Multi-part questions or unclassified
"""

import re
from enum import Enum
from re import Pattern


class QueryType(Enum):
    """Types of queries for adaptive response formatting."""

    DEFINITION = "definition"
    PROCEDURE = "procedure"
    COMPLIANCE = "compliance"
    COMPARISON = "comparison"
    NUMERICAL = "numerical"
    TIMELINE = "timeline"
    SAFETY = "safety"
    ELIGIBILITY = "eligibility"
    COMPLEX = "complex"

    @property
    def formatting_hint(self) -> str:
        """Get formatting hint for this query type."""
        hints = {
            QueryType.DEFINITION: "Start with clear one-sentence definition, then expand",
            QueryType.PROCEDURE: "Use numbered steps with important considerations",
            QueryType.COMPLIANCE: "Cite specific regulations and highlight audit considerations",
            QueryType.COMPARISON: "Use comparison table highlighting key differences",
            QueryType.NUMERICAL: "Lead with the specific number, then provide context",
            QueryType.TIMELINE: "Present chronologically with duration/frequency",
            QueryType.SAFETY: "Use severity classification, list by frequency",
            QueryType.ELIGIBILITY: "Separate inclusion/exclusion in checklist format",
            QueryType.COMPLEX: "Break down into components, address systematically",
        }
        return hints.get(self, "Provide comprehensive response")


class QueryClassifier:
    """
    Classifies queries into semantic categories using pattern matching.

    Uses regex patterns to identify query intent and route to appropriate
    response formatting.
    """

    # Pattern definitions for each query type.
    # ORDER MATTERS: specific domain types are checked before the broad DEFINITION
    # fallback so "What is the process for..." → PROCEDURE, not DEFINITION.
    PATTERNS: dict[QueryType, list[str]] = {
        QueryType.PROCEDURE: [
            r"\bhow to\b",
            r"\bhow do\b",
            r"\bsteps?\b",
            r"\bprocess\b",
            r"\bprocedure\b",
            r"\bworkflow\b",
            r"\bprotocol for\b",
            r"\binstructions?\b",
        ],
        QueryType.COMPLIANCE: [
            r"\bcomplian(ce|t)\b",
            r"\bregulat(ory|ion|ions)\b",
            r"\bFDA\b",
            r"\bEMA\b",
            r"\bICH\b",
            r"\bGCP\b",
            r"\b21\s*CFR\b",
            r"\baudit\b",
            r"\binspection\b",
        ],
        QueryType.COMPARISON: [
            r"\bcompare\b",
            r"\bcomparison\b",
            r"\bdifferen(ce|t|ces)\b",
            r"\bversus\b",
            r"\bvs\.?\b",
            r"\bbetween\b.*\band\b",
            r"\bwhich is better\b",
        ],
        QueryType.NUMERICAL: [
            r"\bhow many\b",
            r"\bcount\b",
            r"\bnumber of\b",
            r"\bpercentage\b",
            r"\bhow much\b",
            r"\bquantity\b",
            r"\btotal\b",
            r"\bfrequency\b",
        ],
        QueryType.TIMELINE: [
            r"\bwhen\b",
            r"\bschedule\b",
            r"\btimeline\b",
            r"\bdeadline\b",
            r"\bduration\b",
            r"\bhow long\b",
            r"\btime frame\b",
            r"\bfrequency\b",
        ],
        QueryType.SAFETY: [
            r"\bsafety\b",
            r"\badverse events?\b",
            r"\badverse reactions?\b",
            r"\bAE\b",
            r"\bSAE\b",
            r"\bside effects?\b",
            r"\brisks?\b",
            r"\btoxicity\b",
            r"\bcontraindications?\b",
        ],
        QueryType.ELIGIBILITY: [
            r"\beligib(le|ility)\b",
            r"\binclusion\b",
            r"\bexclusion\b",
            r"\bcriteria\b",
            r"\bqualify\b",
            r"\benroll(ment)?\b",
            r"\bpatient selection\b",
        ],
        # DEFINITION is last — it is a broad fallback that matches "what is/are"
        # and should only win when no more specific domain type matches first.
        QueryType.DEFINITION: [
            r"\bwhat is\b",
            r"\bwhat are\b",
            r"\bdefine\b",
            r"\bdefinition\b",
            r"\bexplain\b",
            r"\bmean(s|ing)?\b",
            r"\bdescribe\b",
        ],
    }

    # Compiled patterns for efficiency
    _compiled_patterns: dict[QueryType, list[Pattern]] = {}

    @classmethod
    def _compile_patterns(cls) -> None:
        """Compile regex patterns if not already done."""
        if not cls._compiled_patterns:
            for query_type, patterns in cls.PATTERNS.items():
                cls._compiled_patterns[query_type] = [
                    re.compile(pattern, re.IGNORECASE) for pattern in patterns
                ]

    @classmethod
    def classify(cls, query: str) -> QueryType:
        """
        Classify a query into a QueryType category.

        Args:
            query: The user's question/query string

        Returns:
            QueryType enum value representing the query category

        Classification Priority:
            1. Complexity check (multi-sentence/multi-question) — overrides patterns
            2. Pattern matching in priority order (specific domain types before DEFINITION)
            3. Default to DEFINITION
        """
        cls._compile_patterns()
        query_lower = query.lower()

        # Check for complex queries first — multiple questions override type detection
        sentence_count = len([s for s in query.split(".") if s.strip()])
        question_count = query.count("?")

        if sentence_count > 2 or question_count > 1:
            return QueryType.COMPLEX

        # Check each query type's patterns in priority order
        for query_type, patterns in cls._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(query_lower):
                    return query_type

        # Default
        return QueryType.DEFINITION

    @classmethod
    def get_confidence(cls, query: str, query_type: QueryType) -> float:
        """
        Get confidence score for a classification.

        Args:
            query: The query string
            query_type: The classified QueryType

        Returns:
            Float between 0 and 1 indicating confidence
        """
        cls._compile_patterns()

        if query_type not in cls._compiled_patterns:
            return 0.5  # Default confidence for COMPLEX

        patterns = cls._compiled_patterns[query_type]
        matches = sum(1 for p in patterns if p.search(query.lower()))

        # More matches = higher confidence
        return min(1.0, 0.5 + (matches * 0.2))


def classify_query(query: str) -> QueryType:
    """
    Convenience function to classify a query.

    Args:
        query: The user's question/query string

    Returns:
        QueryType enum value
    """
    return QueryClassifier.classify(query)
