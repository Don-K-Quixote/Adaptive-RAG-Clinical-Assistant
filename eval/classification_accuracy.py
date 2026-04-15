"""
Query Classification Accuracy Evaluation
=========================================

Measures how accurately the 9-type query classifier labels queries.
No document, no LLM, no API calls — runs in under 1 second.

Output:
- results/classification_accuracy_results.csv
- results/classification_confusion_matrix.csv
- results/classification_accuracy_summary.txt
"""

import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.personas import UserType, detect_user_type
from src.query_classifier import QueryClassifier, QueryType, classify_query

# ---------------------------------------------------------------------------
# Labeled dataset — 45 queries, 5 per QueryType
# ---------------------------------------------------------------------------

LABELED_QUERY_DATASET: list[dict] = [
    # DEFINITION (5)
    {
        "query": "What is RECIST 1.1?",
        "expected_type": "definition",
        "query_type_label": "DEFINITION",
    },
    {
        "query": "What are target lesions?",
        "expected_type": "definition",
        "query_type_label": "DEFINITION",
    },
    {
        "query": "Define complete response in RECIST criteria",
        "expected_type": "definition",
        "query_type_label": "DEFINITION",
    },
    {
        "query": "Explain what non-target lesions are",
        "expected_type": "definition",
        "query_type_label": "DEFINITION",
    },
    {
        "query": "What does stable disease mean in oncology trials?",
        "expected_type": "definition",
        "query_type_label": "DEFINITION",
    },
    # PROCEDURE (5)
    {
        "query": "How do I measure target lesions?",
        "expected_type": "procedure",
        "query_type_label": "PROCEDURE",
    },
    {
        "query": "What are the steps for reporting adverse events?",
        "expected_type": "procedure",
        "query_type_label": "PROCEDURE",
    },
    {
        "query": "How to perform a CT scan for tumor assessment?",
        "expected_type": "procedure",
        "query_type_label": "PROCEDURE",
    },
    {
        "query": "What is the process for patient randomization?",
        "expected_type": "procedure",
        "query_type_label": "PROCEDURE",
    },
    {
        "query": "Describe the procedure for completing the eligibility checklist",
        "expected_type": "procedure",
        "query_type_label": "PROCEDURE",
    },
    # COMPLIANCE (5)
    {
        "query": "What are the FDA requirements for informed consent?",
        "expected_type": "compliance",
        "query_type_label": "COMPLIANCE",
    },
    {
        "query": "What GCP guidelines apply to adverse event reporting?",
        "expected_type": "compliance",
        "query_type_label": "COMPLIANCE",
    },
    {
        "query": "What are the ICH-E6 requirements for documentation?",
        "expected_type": "compliance",
        "query_type_label": "COMPLIANCE",
    },
    {
        "query": "How does 21 CFR Part 11 apply to electronic records?",
        "expected_type": "compliance",
        "query_type_label": "COMPLIANCE",
    },
    {
        "query": "What are the regulatory requirements for protocol deviations?",
        "expected_type": "compliance",
        "query_type_label": "COMPLIANCE",
    },
    # COMPARISON (5)
    {
        "query": "Compare CT and MRI for tumor assessment",
        "expected_type": "comparison",
        "query_type_label": "COMPARISON",
    },
    {
        "query": "What is the difference between PR and CR?",
        "expected_type": "comparison",
        "query_type_label": "COMPARISON",
    },
    {
        "query": "How does RECIST 1.1 compare to iRECIST?",
        "expected_type": "comparison",
        "query_type_label": "COMPARISON",
    },
    {
        "query": "Difference between SAE and AE in clinical trials",
        "expected_type": "comparison",
        "query_type_label": "COMPARISON",
    },
    {
        "query": "Compare open-label versus blinded study designs",
        "expected_type": "comparison",
        "query_type_label": "COMPARISON",
    },
    # NUMERICAL (5)
    {
        "query": "How many target lesions can be measured per organ?",
        "expected_type": "numerical",
        "query_type_label": "NUMERICAL",
    },
    {
        "query": "What is the minimum size for target lesions?",
        "expected_type": "numerical",
        "query_type_label": "NUMERICAL",
    },
    {
        "query": "How many baseline scans are required?",
        "expected_type": "numerical",
        "query_type_label": "NUMERICAL",
    },
    {
        "query": "What percentage improvement defines partial response?",
        "expected_type": "numerical",
        "query_type_label": "NUMERICAL",
    },
    {
        "query": "What is the total number of target lesions allowed per RECIST?",
        "expected_type": "numerical",
        "query_type_label": "NUMERICAL",
    },
    # TIMELINE (5)
    {
        "query": "What is the imaging schedule for this study?",
        "expected_type": "timeline",
        "query_type_label": "TIMELINE",
    },
    {
        "query": "When should adverse events be reported?",
        "expected_type": "timeline",
        "query_type_label": "TIMELINE",
    },
    {
        "query": "What is the duration of the treatment period?",
        "expected_type": "timeline",
        "query_type_label": "TIMELINE",
    },
    {
        "query": "How long is the follow-up period after treatment?",
        "expected_type": "timeline",
        "query_type_label": "TIMELINE",
    },
    {
        "query": "What is the deadline for submitting the final assessment?",
        "expected_type": "timeline",
        "query_type_label": "TIMELINE",
    },
    # SAFETY (5)
    {
        "query": "What are the safety stopping rules for this trial?",
        "expected_type": "safety",
        "query_type_label": "SAFETY",
    },
    {
        "query": "How are adverse events classified by severity?",
        "expected_type": "safety",
        "query_type_label": "SAFETY",
    },
    {
        "query": "What are the known toxicities of this treatment?",
        "expected_type": "safety",
        "query_type_label": "SAFETY",
    },
    {
        "query": "What are the contraindications for patient enrollment?",
        "expected_type": "safety",
        "query_type_label": "SAFETY",
    },
    {
        "query": "How should serious adverse events be managed and reported?",
        "expected_type": "safety",
        "query_type_label": "SAFETY",
    },
    # ELIGIBILITY (5)
    {
        "query": "What are the inclusion criteria for this study?",
        "expected_type": "eligibility",
        "query_type_label": "ELIGIBILITY",
    },
    {
        "query": "What exclusion criteria prevent enrollment?",
        "expected_type": "eligibility",
        "query_type_label": "ELIGIBILITY",
    },
    {
        "query": "Who is eligible to participate in this clinical trial?",
        "expected_type": "eligibility",
        "query_type_label": "ELIGIBILITY",
    },
    {
        "query": "What criteria must patients meet for enrollment?",
        "expected_type": "eligibility",
        "query_type_label": "ELIGIBILITY",
    },
    {
        "query": "Which patients do not qualify for the study?",
        "expected_type": "eligibility",
        "query_type_label": "ELIGIBILITY",
    },
    # COMPLEX (5)
    {
        "query": "What are the imaging requirements and how do they compare to standard care? How often are scans required?",
        "expected_type": "complex",
        "query_type_label": "COMPLEX",
    },
    {
        "query": "Explain the response criteria. What defines complete response and how is it confirmed?",
        "expected_type": "complex",
        "query_type_label": "COMPLEX",
    },
    {
        "query": "What are the safety monitoring procedures and when should the trial be stopped for safety?",
        "expected_type": "complex",
        "query_type_label": "COMPLEX",
    },
    {
        "query": "Describe the study design, primary endpoints, and statistical methodology used in this trial.",
        "expected_type": "complex",
        "query_type_label": "COMPLEX",
    },
    {
        "query": "What are the inclusion criteria and how do the safety monitoring procedures interact with enrollment?",
        "expected_type": "complex",
        "query_type_label": "COMPLEX",
    },
]


# ---------------------------------------------------------------------------
# Expertise classification dataset — 25 user profiles, 5 per UserType.
# Each profile is a dict suitable for detect_user_type(user_profile).
# expected_user_type is the ground-truth UserType.value string.
# ---------------------------------------------------------------------------

LABELED_EXPERTISE_DATASET: list[dict] = [
    # NOVICE (5) — role keywords trigger the "novice" branch in detect_user_type
    {"role": "intern", "experience_years": 0, "expected_user_type": "novice"},
    {"role": "trainee", "experience_years": 0, "expected_user_type": "novice"},
    {"role": "junior assistant", "experience_years": 1, "expected_user_type": "novice"},
    {"role": "new hire", "experience_years": 0, "expected_user_type": "novice"},
    {"role": "entry level coordinator", "experience_years": 1, "expected_user_type": "novice"},
    # INTERMEDIATE (5) — no keyword match; experience 3-4 years → default INTERMEDIATE
    {
        "role": "clinical research coordinator",
        "experience_years": 3,
        "expected_user_type": "intermediate",
    },
    {"role": "study coordinator", "experience_years": 4, "expected_user_type": "intermediate"},
    {"role": "data analyst", "experience_years": 4, "expected_user_type": "intermediate"},
    {
        "role": "clinical research associate",
        "experience_years": 3,
        "expected_user_type": "intermediate",
    },
    {"role": "study monitor", "experience_years": 4, "expected_user_type": "intermediate"},
    # EXPERT (5) — role keywords trigger the "expert" branch
    {"role": "senior investigator", "experience_years": 10, "expected_user_type": "expert"},
    {"role": "principal investigator", "experience_years": 15, "expected_user_type": "expert"},
    {"role": "lead oncologist", "experience_years": 12, "expected_user_type": "expert"},
    {"role": "specialist radiologist", "experience_years": 8, "expected_user_type": "expert"},
    {"role": "senior physician", "experience_years": 10, "expected_user_type": "expert"},
    # REGULATORY (5) — "regulatory" / "compliance" / "quality" / "audit" keywords
    {
        "role": "regulatory affairs specialist",
        "experience_years": 7,
        "expected_user_type": "regulatory",
    },
    {"role": "compliance officer", "experience_years": 8, "expected_user_type": "regulatory"},
    {
        "role": "quality assurance manager",
        "experience_years": 6,
        "expected_user_type": "regulatory",
    },
    {"role": "regulatory inspector", "experience_years": 9, "expected_user_type": "regulatory"},
    {"role": "audit specialist", "experience_years": 5, "expected_user_type": "regulatory"},
    # EXECUTIVE (5) — "chief" / "vice president" / "executive" / "sponsor" / "head of" keywords
    {"role": "chief medical officer", "experience_years": 20, "expected_user_type": "executive"},
    {
        "role": "vice president clinical operations",
        "experience_years": 18,
        "expected_user_type": "executive",
    },
    {"role": "executive director", "experience_years": 15, "expected_user_type": "executive"},
    {"role": "sponsor representative", "experience_years": 12, "expected_user_type": "executive"},
    {
        "role": "head of clinical development",
        "experience_years": 16,
        "expected_user_type": "executive",
    },
]

# Combined Accuracy weights (query-type and expertise components)
COMBINED_ACCURACY_W1 = 0.6  # weight for query-type accuracy
COMBINED_ACCURACY_W2 = 0.4  # weight for expertise classification accuracy


def run_expertise_accuracy(
    labeled_dataset: list[dict] | None = None,
) -> pd.DataFrame:
    """
    Evaluate how accurately detect_user_type() classifies user profiles.

    Args:
        labeled_dataset: Optional override for LABELED_EXPERTISE_DATASET.

    Returns:
        DataFrame with columns: role, experience_years, expected_user_type,
        predicted_user_type, is_correct.
    """
    dataset = labeled_dataset if labeled_dataset is not None else LABELED_EXPERTISE_DATASET

    rows = []
    for item in dataset:
        profile = {"role": item["role"], "experience_years": item["experience_years"]}
        expected = item["expected_user_type"]
        predicted = detect_user_type(profile).value
        rows.append(
            {
                "role": item["role"],
                "experience_years": item["experience_years"],
                "expected_user_type": expected,
                "predicted_user_type": predicted,
                "is_correct": predicted == expected,
            }
        )

    return pd.DataFrame(rows)


def run_classification_accuracy(
    output_dir: str = "results",
    labeled_dataset: list[dict] | None = None,
) -> pd.DataFrame:
    """
    Evaluate query classifier accuracy against the labeled dataset.

    Args:
        output_dir: Directory for output files.
        labeled_dataset: Optional override for the default labeled dataset.

    Returns:
        DataFrame with columns: query, expected_type, predicted_type,
        confidence, is_correct.
    """
    os.makedirs(output_dir, exist_ok=True)

    dataset = labeled_dataset if labeled_dataset is not None else LABELED_QUERY_DATASET

    rows = []
    for item in dataset:
        query = item["query"]
        expected = item["expected_type"]

        predicted_qtype = classify_query(query)
        predicted = predicted_qtype.value
        confidence = QueryClassifier.get_confidence(query, predicted_qtype)

        rows.append(
            {
                "query": query,
                "expected_type": expected,
                "predicted_type": predicted,
                "confidence": round(confidence, 3),
                "is_correct": predicted == expected,
            }
        )

    df = pd.DataFrame(rows)

    # Save main results
    csv_path = os.path.join(output_dir, "classification_accuracy_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"[SAVED] {csv_path}")

    # Build confusion matrix
    all_types = [qt.value for qt in QueryType]
    confusion = pd.crosstab(
        df["expected_type"],
        df["predicted_type"],
        rownames=["Actual"],
        colnames=["Predicted"],
    ).reindex(index=all_types, columns=all_types, fill_value=0)

    confusion_path = os.path.join(output_dir, "classification_confusion_matrix.csv")
    confusion.to_csv(confusion_path)
    print(f"[SAVED] {confusion_path}")

    # Expertise classification accuracy
    df_expertise = run_expertise_accuracy()
    expertise_csv_path = os.path.join(output_dir, "expertise_accuracy_results.csv")
    df_expertise.to_csv(expertise_csv_path, index=False)
    print(f"[SAVED] {expertise_csv_path}")

    # Combined accuracy
    query_type_acc = df["is_correct"].mean()
    expertise_acc = df_expertise["is_correct"].mean()
    combined_accuracy = COMBINED_ACCURACY_W1 * query_type_acc + COMBINED_ACCURACY_W2 * expertise_acc

    # Generate summary
    summary_path = os.path.join(output_dir, "classification_accuracy_summary.txt")
    _write_summary(df, confusion, df_expertise, combined_accuracy, summary_path)
    print(f"[SAVED] {summary_path}")

    print(f"\n[RESULT] Query type accuracy: {query_type_acc:.1%}")
    print(f"[RESULT] Expertise accuracy:   {expertise_acc:.1%}")
    print(
        f"[RESULT] Combined accuracy:    {combined_accuracy:.1%}  "
        f"({COMBINED_ACCURACY_W1}×{query_type_acc:.3f} + {COMBINED_ACCURACY_W2}×{expertise_acc:.3f})"
    )

    return df


def _write_summary(
    df: pd.DataFrame,
    confusion: pd.DataFrame,
    df_expertise: pd.DataFrame,
    combined_accuracy: float,
    output_path: str,
) -> None:
    """Write a human-readable accuracy summary report."""
    overall_accuracy = df["is_correct"].mean()
    avg_confidence = df["confidence"].mean()
    expertise_accuracy = df_expertise["is_correct"].mean()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("        QUERY CLASSIFICATION ACCURACY REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write(
            f"Query Type Accuracy:   {overall_accuracy:.1%}  ({df['is_correct'].sum()}/{len(df)} correct)\n"
        )
        f.write(
            f"Expertise Accuracy:    {expertise_accuracy:.1%}  "
            f"({df_expertise['is_correct'].sum()}/{len(df_expertise)} correct)\n"
        )
        f.write(
            f"Combined Accuracy:     {combined_accuracy:.1%}  "
            f"({COMBINED_ACCURACY_W1}×{overall_accuracy:.3f} + "
            f"{COMBINED_ACCURACY_W2}×{expertise_accuracy:.3f})\n"
        )
        f.write(f"Avg Confidence:        {avg_confidence:.3f}\n\n")

        # Per-type accuracy
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  PER-TYPE ACCURACY" + " " * 49 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(
            f"{'Query Type':<20} {'Correct':<10} {'Total':<8} {'Accuracy':<12} {'Avg Conf':<10}\n"
        )
        f.write("-" * 65 + "\n")

        for qtype in sorted(df["expected_type"].unique()):
            type_df = df[df["expected_type"] == qtype]
            correct = type_df["is_correct"].sum()
            total = len(type_df)
            acc = correct / total if total else 0
            conf = type_df["confidence"].mean()
            f.write(f"{qtype:<20} {correct:<10} {total:<8} {acc:<12.1%} {conf:<10.3f}\n")

        f.write("\n")

        # Expertise classification breakdown
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  EXPERTISE CLASSIFICATION ACCURACY" + " " * 33 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(f"{'User Type':<20} {'Correct':<10} {'Total':<8} {'Accuracy':<12}\n")
        f.write("-" * 55 + "\n")

        for utype in [ut.value for ut in UserType]:
            udata = df_expertise[df_expertise["expected_user_type"] == utype]
            if udata.empty:
                continue
            correct = udata["is_correct"].sum()
            total = len(udata)
            acc = correct / total if total else 0
            f.write(f"{utype:<20} {correct:<10} {total:<8} {acc:<12.1%}\n")

        f.write(
            f"\nCombined Accuracy = {COMBINED_ACCURACY_W1}×QueryTypeAcc + "
            f"{COMBINED_ACCURACY_W2}×ExpertiseAcc = {combined_accuracy:.1%}\n\n"
        )

        # Top misclassification pairs
        wrong = df[~df["is_correct"]]
        if not wrong.empty:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  TOP MISCLASSIFICATIONS" + " " * 44 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            pairs = (
                wrong.groupby(["expected_type", "predicted_type"])
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
                .head(10)
            )
            for _, row in pairs.iterrows():
                f.write(
                    f"  {row['expected_type']} → {row['predicted_type']}: {row['count']} time(s)\n"
                )
            f.write("\n")

        f.write("=" * 70 + "\n")
        f.write("                          END OF REPORT\n")
        f.write("=" * 70 + "\n")


if __name__ == "__main__":
    run_classification_accuracy()
