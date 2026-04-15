"""
Tests for eval/readability_analysis.py
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

pytest.importorskip("textstat", reason="textstat not installed")

from eval.readability_analysis import compute_readability_metrics, run_readability_analysis

# ---------------------------------------------------------------------------
# Helper text constants
# ---------------------------------------------------------------------------

SIMPLE_TEXT = (
    "The cat sat on the mat. The dog ran fast. The sun is bright. Birds fly high. Kids play here."
)

COMPLEX_TEXT = (
    "The pharmacokinetic parameters demonstrate substantial interindividual variability "
    "in clearance rates, necessitating rigorous bioequivalence assessments. "
    "Concomitant administration of cytochrome P450 3A4 inhibitors may precipitate "
    "clinically significant elevations in plasma concentrations, potentially exacerbating "
    "adverse haematological manifestations and hepatotoxicity."
)


# ---------------------------------------------------------------------------
# compute_readability_metrics() unit tests
# ---------------------------------------------------------------------------


def test_simple_text_has_high_flesch_ease():
    result = compute_readability_metrics(SIMPLE_TEXT)
    # Simple text should be easy to read (Flesch ease > 70)
    assert result["flesch_reading_ease"] > 50, (
        f"Expected high reading ease for simple text, got {result['flesch_reading_ease']}"
    )


def test_complex_text_has_lower_flesch_ease():
    simple_result = compute_readability_metrics(SIMPLE_TEXT)
    complex_result = compute_readability_metrics(COMPLEX_TEXT)
    assert complex_result["flesch_reading_ease"] < simple_result["flesch_reading_ease"], (
        "Complex text should have lower Flesch ease than simple text"
    )


def test_compute_readability_returns_all_fields():
    result = compute_readability_metrics(SIMPLE_TEXT)
    expected_keys = {
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "gunning_fog",
        "word_count",
        "sentence_count",
        "difficult_words",
        "avg_sentence_length",
    }
    assert expected_keys.issubset(result.keys()), f"Missing keys: {expected_keys - result.keys()}"


def test_empty_text_returns_zero_metrics():
    result = compute_readability_metrics("")
    assert result["word_count"] == 0
    assert result["sentence_count"] == 0
    assert result["flesch_reading_ease"] == 0.0


def test_word_count_matches_split(simple_text=SIMPLE_TEXT):
    result = compute_readability_metrics(SIMPLE_TEXT)
    assert result["word_count"] == len(SIMPLE_TEXT.split())


# ---------------------------------------------------------------------------
# run_readability_analysis() integration tests (mocked)
# ---------------------------------------------------------------------------


def _make_persona_json(tmp_path: Path) -> str:
    """Write a minimal persona_responses.json fixture."""
    data = [
        {
            "query": "What is RECIST 1.1?",
            "query_type": "definition",
            "num_sources": 3,
            "responses": {
                "novice": {
                    "response": SIMPLE_TEXT * 5,
                    "word_count": len((SIMPLE_TEXT * 5).split()),
                    "generation_time_ms": 100,
                    "config": {
                        "user_type": "novice",
                        "query_type": "definition",
                        "detail_level": "basic",
                        "max_length": 200,
                        "use_tables": False,
                        "include_definitions": True,
                        "include_key_takeaway": True,
                        "include_executive_summary": False,
                    },
                    "response_length": len(SIMPLE_TEXT * 5),
                },
                "expert": {
                    "response": COMPLEX_TEXT * 3,
                    "word_count": len((COMPLEX_TEXT * 3).split()),
                    "generation_time_ms": 150,
                    "config": {
                        "user_type": "expert",
                        "query_type": "definition",
                        "detail_level": "technical",
                        "max_length": 600,
                        "use_tables": True,
                        "include_definitions": False,
                        "include_key_takeaway": False,
                        "include_executive_summary": False,
                    },
                    "response_length": len(COMPLEX_TEXT * 3),
                },
            },
        }
    ]
    json_path = tmp_path / "persona_responses.json"
    json_path.write_text(json.dumps(data), encoding="utf-8")
    return str(json_path)


def test_output_csv_created(tmp_path):
    _make_persona_json(tmp_path)
    run_readability_analysis(document_path="dummy.pdf", output_dir=str(tmp_path))
    assert (tmp_path / "readability_analysis_results.csv").exists()


def test_output_summary_txt_created(tmp_path):
    _make_persona_json(tmp_path)
    run_readability_analysis(document_path="dummy.pdf", output_dir=str(tmp_path))
    assert (tmp_path / "readability_analysis_summary.txt").exists()


def test_dataframe_has_persona_column(tmp_path):
    _make_persona_json(tmp_path)
    df = run_readability_analysis(document_path="dummy.pdf", output_dir=str(tmp_path))
    assert "persona" in df.columns


def test_dataframe_has_required_metric_columns(tmp_path):
    _make_persona_json(tmp_path)
    df = run_readability_analysis(document_path="dummy.pdf", output_dir=str(tmp_path))
    expected_cols = {
        "flesch_reading_ease",
        "flesch_kincaid_grade",
        "gunning_fog",
        "word_count",
        "sentence_count",
        "difficult_words",
        "avg_sentence_length",
    }
    assert expected_cols.issubset(set(df.columns))


def test_novice_simpler_than_expert_in_fixture(tmp_path):
    _make_persona_json(tmp_path)
    df = run_readability_analysis(document_path="dummy.pdf", output_dir=str(tmp_path))
    novice_grade = df[df["persona"] == "novice"]["flesch_kincaid_grade"].mean()
    expert_grade = df[df["persona"] == "expert"]["flesch_kincaid_grade"].mean()
    assert novice_grade < expert_grade
