"""
Tests for eval/classification_accuracy.py
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from eval.classification_accuracy import LABELED_QUERY_DATASET, run_classification_accuracy
from src.query_classifier import QueryType

# ---------------------------------------------------------------------------
# Dataset integrity tests
# ---------------------------------------------------------------------------


def test_dataset_has_45_queries():
    assert len(LABELED_QUERY_DATASET) == 45


def test_each_type_has_5_queries():
    counts = Counter(item["expected_type"] for item in LABELED_QUERY_DATASET)
    for qtype, count in counts.items():
        assert count == 5, f"Expected 5 queries for type '{qtype}', got {count}"


def test_all_required_keys_present():
    required_keys = {"query", "expected_type", "query_type_label"}
    for item in LABELED_QUERY_DATASET:
        missing = required_keys - item.keys()
        assert not missing, f"Missing keys {missing} in item: {item}"


def test_expected_types_are_valid():
    valid_values = {qt.value for qt in QueryType}
    for item in LABELED_QUERY_DATASET:
        assert item["expected_type"] in valid_values, (
            f"Invalid expected_type '{item['expected_type']}' — valid values: {valid_values}"
        )


def test_nine_distinct_types_present():
    types = {item["expected_type"] for item in LABELED_QUERY_DATASET}
    assert len(types) == 9, f"Expected 9 distinct types, got {len(types)}: {types}"


# ---------------------------------------------------------------------------
# Function output tests
# ---------------------------------------------------------------------------


def test_returns_dataframe_with_required_columns(tmp_path):
    df = run_classification_accuracy(output_dir=str(tmp_path))
    required_cols = {"query", "expected_type", "predicted_type", "confidence", "is_correct"}
    assert required_cols.issubset(set(df.columns))


def test_returns_correct_row_count(tmp_path):
    df = run_classification_accuracy(output_dir=str(tmp_path))
    assert len(df) == 45


def test_confidence_values_in_valid_range(tmp_path):
    df = run_classification_accuracy(output_dir=str(tmp_path))
    assert df["confidence"].between(0.0, 1.0).all()


def test_is_correct_is_boolean(tmp_path):
    df = run_classification_accuracy(output_dir=str(tmp_path))
    assert df["is_correct"].dtype == bool


def test_output_csv_created(tmp_path):
    run_classification_accuracy(output_dir=str(tmp_path))
    assert (tmp_path / "classification_accuracy_results.csv").exists()


def test_confusion_matrix_csv_created(tmp_path):
    run_classification_accuracy(output_dir=str(tmp_path))
    assert (tmp_path / "classification_confusion_matrix.csv").exists()


def test_summary_txt_created(tmp_path):
    run_classification_accuracy(output_dir=str(tmp_path))
    assert (tmp_path / "classification_accuracy_summary.txt").exists()


def test_overall_accuracy_above_70_percent(tmp_path):
    """Baseline quality bar: the classifier must be at least 70% accurate."""
    df = run_classification_accuracy(output_dir=str(tmp_path))
    overall_accuracy = df["is_correct"].mean()
    assert overall_accuracy >= 0.70, (
        f"Classifier accuracy {overall_accuracy:.1%} is below the 70% quality bar"
    )


def test_custom_dataset_is_used(tmp_path):
    custom_dataset = [
        {
            "query": "What is a randomized trial?",
            "expected_type": "definition",
            "query_type_label": "DEFINITION",
        },
        {
            "query": "How many patients are needed?",
            "expected_type": "numerical",
            "query_type_label": "NUMERICAL",
        },
    ]
    df = run_classification_accuracy(output_dir=str(tmp_path), labeled_dataset=custom_dataset)
    assert len(df) == 2
