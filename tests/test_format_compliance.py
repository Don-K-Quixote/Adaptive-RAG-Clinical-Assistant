"""
Tests for eval/format_compliance.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.format_compliance import (
    FORMAT_RULES,
    check_rule,
    compute_compliance_score,
    run_format_compliance,
)

# ---------------------------------------------------------------------------
# check_rule() unit tests
# ---------------------------------------------------------------------------


def test_numbered_steps_detected():
    text = "1. Load the document\n2. Chunk the text\n3. Embed the chunks"
    result = check_rule("procedure_has_numbered_steps", text, "procedure", "expert")
    assert result is True


def test_numbered_steps_not_detected_without_list():
    text = "The procedure involves loading the document and then chunking the text."
    result = check_rule("procedure_has_numbered_steps", text, "procedure", "expert")
    assert result is False


def test_numbered_steps_not_applicable_for_other_query_type():
    text = "1. Step one\n2. Step two"
    result = check_rule("procedure_has_numbered_steps", text, "definition", "expert")
    assert result is None


def test_markdown_table_detected():
    text = "| Column A | Column B | Column C |\n|---|---|---|\n| val1 | val2 | val3 |"
    result = check_rule("comparison_has_table", text, "comparison", "intermediate")
    assert result is True


def test_markdown_table_not_detected_in_plain_text():
    text = "CT and MRI are both imaging modalities used for tumor assessment."
    result = check_rule("comparison_has_table", text, "comparison", "intermediate")
    assert result is False


def test_key_takeaway_detected_with_emoji():
    text = "The target lesion can be up to 5 per organ.\n\n📌 Key Takeaway: Always measure the longest diameter."
    result = check_rule("novice_has_key_takeaway", text, "definition", "novice")
    assert result is True


def test_key_takeaway_detected_without_emoji():
    text = "Here is a summary.\n\nKey Takeaway: Use millimetres for measurements."
    result = check_rule("novice_has_key_takeaway", text, "definition", "novice")
    assert result is True


def test_key_takeaway_not_applicable_for_expert():
    text = "📌 Key Takeaway: Always measure."
    result = check_rule("novice_has_key_takeaway", text, "definition", "expert")
    assert result is None


def test_regulatory_citation_detected():
    text = "Per FDA guidance, informed consent must be obtained before any study procedures."
    result = check_rule("compliance_cites_regulation", text, "compliance", "regulatory")
    assert result is True


def test_regulatory_citation_not_applicable_for_definition():
    text = "FDA requirements are strict."
    result = check_rule("compliance_cites_regulation", text, "definition", "novice")
    assert result is None


def test_severity_classification_detected():
    text = "Grade 3 toxicity was observed in 15% of patients."
    result = check_rule("safety_contains_severity", text, "safety", "expert")
    assert result is True


def test_severity_mild_detected():
    text = "Mild adverse events were reported."
    result = check_rule("safety_contains_severity", text, "safety", "novice")
    assert result is True


def test_timeframe_detected():
    text = "Imaging should be performed within 28 days of randomization."
    result = check_rule("timeline_contains_timeframe", text, "timeline", "intermediate")
    assert result is True


def test_timeframe_not_detected_without_number():
    text = "Imaging should be performed at regular intervals."
    result = check_rule("timeline_contains_timeframe", text, "timeline", "intermediate")
    assert result is False


def test_parenthetical_definition_detected():
    text = "RECIST (Response Evaluation Criteria in Solid Tumors) is used to assess treatment response."
    result = check_rule("novice_defines_terms", text, "definition", "novice")
    assert result is True


def test_eligibility_inclusion_detected():
    text = "Patients are eligible if they meet the inclusion criteria for the study."
    result = check_rule("eligibility_has_inclusion", text, "eligibility", "novice")
    assert result is True


def test_eligibility_exclusion_detected():
    text = "Patients with prior treatment are excluded from participation."
    result = check_rule("eligibility_has_exclusion", text, "eligibility", "novice")
    assert result is True


# ---------------------------------------------------------------------------
# compute_compliance_score() unit tests
# ---------------------------------------------------------------------------


def test_compliance_score_zero_for_bare_prose():
    """Plain prose for a novice/procedure combo should have low compliance."""
    text = "The process involves several stages of assessment."
    score = compute_compliance_score(text, "procedure", "novice")
    # Applicable rules exist but none should pass with bare prose
    assert score < 0.5


def test_perfect_score_for_full_novice_procedure_response():
    """A well-crafted novice procedure response should score above 0.8."""
    text = (
        "Here is how to measure target lesions (tumors being tracked in the study):\n\n"
        "1. Identify the lesion on the CT scan\n"
        "2. Measure the longest diameter in millimetres\n"
        "3. Record the measurement in the eCRF system\n\n"
        "- Always use the same imaging modality\n"
        "- Measure at baseline and all follow-up visits\n"
        "- Document any technical issues\n\n"
        "📌 Key Takeaway: Consistent measurement with RECIST criteria ensures accurate response assessment."
    )
    score = compute_compliance_score(text, "procedure", "novice")
    assert score > 0.8, (
        f"Expected compliance > 0.8 for ideal novice/procedure response, got {score:.2f}"
    )


def test_compliance_score_between_0_and_1():
    texts = [
        ("plain text with no formatting", "definition", "intermediate"),
        ("1. Step one\n2. Step two\n📌 Key Takeaway: Done", "procedure", "novice"),
    ]
    for text, qtype, persona in texts:
        score = compute_compliance_score(text, qtype, persona)
        assert 0.0 <= score <= 1.0, f"Score {score} out of range for ({qtype}, {persona})"


def test_no_applicable_rules_returns_zero():
    # COMPLEX query type has no specific rules in FORMAT_RULES
    score = compute_compliance_score("some text", "complex", "intermediate")
    # Only intermediate_has_example would apply; this text has no "for example"
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# FORMAT_RULES integrity tests
# ---------------------------------------------------------------------------


def test_all_rules_have_required_keys():
    required = {"condition_key", "condition_value", "pattern", "flags", "description"}
    for rule_name, rule in FORMAT_RULES.items():
        missing = required - rule.keys()
        assert not missing, f"Rule '{rule_name}' missing keys: {missing}"


def test_sixteen_rules_defined():
    assert len(FORMAT_RULES) == 16


# ---------------------------------------------------------------------------
# run_format_compliance() integration tests (fixture-based)
# ---------------------------------------------------------------------------


def _make_persona_json(tmp_path: Path) -> str:
    """Write a minimal persona_responses.json fixture."""
    data = [
        {
            "query": "How do I measure target lesions?",
            "query_type": "procedure",
            "num_sources": 3,
            "responses": {
                "novice": {
                    "response": (
                        "1. Identify the lesion\n2. Measure the longest diameter\n"
                        "- Use a calibrated ruler\n"
                        "📌 Key Takeaway: Measure consistently (same visit, same method)."
                    ),
                    "word_count": 25,
                    "generation_time_ms": 100,
                    "config": {
                        "user_type": "novice",
                        "query_type": "procedure",
                        "detail_level": "basic",
                        "max_length": 200,
                        "use_tables": False,
                        "include_definitions": True,
                        "include_key_takeaway": True,
                        "include_executive_summary": False,
                    },
                    "response_length": 200,
                },
                "expert": {
                    "response": (
                        "Per RECIST 1.1 and CTCAE guidelines, target lesions are measured "
                        "using the longest unidimensional diameter. ICH-GCP compliance "
                        "requires documented measurement methodology."
                    ),
                    "word_count": 30,
                    "generation_time_ms": 120,
                    "config": {
                        "user_type": "expert",
                        "query_type": "procedure",
                        "detail_level": "technical",
                        "max_length": 600,
                        "use_tables": True,
                        "include_definitions": False,
                        "include_key_takeaway": False,
                        "include_executive_summary": False,
                    },
                    "response_length": 300,
                },
            },
        }
    ]
    json_path = tmp_path / "persona_responses.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    return str(json_path)


def test_output_csv_created(tmp_path):
    _make_persona_json(tmp_path)
    run_format_compliance(document_path="dummy.pdf", output_dir=str(tmp_path))
    assert (tmp_path / "format_compliance_results.csv").exists()


def test_output_summary_txt_created(tmp_path):
    _make_persona_json(tmp_path)
    run_format_compliance(document_path="dummy.pdf", output_dir=str(tmp_path))
    assert (tmp_path / "format_compliance_summary.txt").exists()


def test_dataframe_has_compliance_score_column(tmp_path):
    _make_persona_json(tmp_path)
    df = run_format_compliance(document_path="dummy.pdf", output_dir=str(tmp_path))
    assert "compliance_score" in df.columns


def test_dataframe_has_rule_columns(tmp_path):
    _make_persona_json(tmp_path)
    df = run_format_compliance(document_path="dummy.pdf", output_dir=str(tmp_path))
    for rule_name in FORMAT_RULES:
        assert rule_name in df.columns, f"Missing rule column: {rule_name}"


def test_novice_compliance_score_positive(tmp_path):
    _make_persona_json(tmp_path)
    df = run_format_compliance(document_path="dummy.pdf", output_dir=str(tmp_path))
    novice_score = df[df["persona"] == "novice"]["compliance_score"].iloc[0]
    assert novice_score > 0.0
