"""
Tests for eval/adaptive_vs_generic.py

These tests cover dataset/constant integrity and the generic prompt builder.
The full run_adaptive_vs_generic() function requires a live PDF and LLM and
is therefore excluded from the unit test suite.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.adaptive_vs_generic import (
    COMPARISON_QUERIES,
    PERSONA_GRADE_TARGETS,
    build_generic_prompt,
)

# ---------------------------------------------------------------------------
# COMPARISON_QUERIES dataset integrity tests
# ---------------------------------------------------------------------------


def test_comparison_queries_has_25_items():
    assert len(COMPARISON_QUERIES) == 25


def test_all_personas_represented():
    personas = {item["persona"] for item in COMPARISON_QUERIES}
    expected = {"novice", "intermediate", "expert", "regulatory", "executive"}
    assert personas == expected


def test_each_persona_has_5_queries():
    counts = Counter(item["persona"] for item in COMPARISON_QUERIES)
    for persona, count in counts.items():
        assert count == 5, f"Expected 5 queries for persona '{persona}', got {count}"


def test_all_required_keys_present():
    required = {"query", "type", "persona"}
    for item in COMPARISON_QUERIES:
        missing = required - item.keys()
        assert not missing, f"Missing keys {missing} in item: {item}"


def test_queries_are_non_empty_strings():
    for item in COMPARISON_QUERIES:
        assert isinstance(item["query"], str) and item["query"].strip()
        assert isinstance(item["type"], str) and item["type"].strip()
        assert isinstance(item["persona"], str) and item["persona"].strip()


# ---------------------------------------------------------------------------
# PERSONA_GRADE_TARGETS integrity tests
# ---------------------------------------------------------------------------


def test_persona_grade_targets_all_present():
    expected_personas = {"novice", "intermediate", "expert", "regulatory", "executive"}
    assert set(PERSONA_GRADE_TARGETS.keys()) == expected_personas


def test_novice_grade_below_expert_grade():
    novice_max = PERSONA_GRADE_TARGETS["novice"][1]
    expert_min = PERSONA_GRADE_TARGETS["expert"][0]
    assert novice_max < expert_min, (
        f"Novice max FK grade ({novice_max}) should be below expert min ({expert_min})"
    )


def test_grade_target_tuples_are_ordered():
    for persona, (low, high) in PERSONA_GRADE_TARGETS.items():
        assert low < high, f"Grade target for '{persona}' is inverted: ({low}, {high})"


# ---------------------------------------------------------------------------
# build_generic_prompt() unit tests
# ---------------------------------------------------------------------------


def test_build_generic_prompt_contains_context_and_query():
    context = "RECIST 1.1 defines tumor measurement criteria."
    query = "What is RECIST 1.1?"
    prompt = build_generic_prompt(context, query)
    assert context in prompt
    assert query in prompt


def test_build_generic_prompt_has_no_persona_instructions():
    """The generic prompt must not contain any persona/audience keywords."""
    context = "Some clinical context."
    query = "What is the imaging schedule?"
    prompt = build_generic_prompt(context, query)
    persona_keywords = [
        "NOVICE",
        "EXPERT",
        "INTERMEDIATE",
        "REGULATORY",
        "EXECUTIVE",
        "AUDIENCE",
        "expertise",
        "detail level",
    ]
    for keyword in persona_keywords:
        assert keyword not in prompt, (
            f"Generic prompt should not contain persona keyword '{keyword}'"
        )


def test_build_generic_prompt_has_no_query_type_instructions():
    """The generic prompt must not contain query-type-specific formatting hints."""
    context = "Treatment response criteria."
    query = "Compare CR and PR."
    prompt = build_generic_prompt(context, query)
    formatting_keywords = [
        "numbered steps",
        "comparison table",
        "bullet points",
        "key takeaway",
        "executive summary",
    ]
    for keyword in formatting_keywords:
        assert keyword.lower() not in prompt.lower(), (
            f"Generic prompt should not contain formatting hint '{keyword}'"
        )


def test_build_generic_prompt_ends_with_answer_marker():
    prompt = build_generic_prompt("context", "query?")
    assert prompt.strip().endswith("Answer:")


def test_build_generic_prompt_returns_string():
    result = build_generic_prompt("ctx", "q")
    assert isinstance(result, str)
