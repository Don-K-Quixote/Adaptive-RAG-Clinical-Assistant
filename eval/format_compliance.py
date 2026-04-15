"""
Format Compliance Evaluation
==============================

Proves that adaptive prompt instructions are followed:
numbered steps appear for procedures, tables for comparisons,
key takeaways for novices, etc.

Reads persona_responses.json if present (zero LLM calls).
Generates responses from scratch otherwise.

Output:
- results/format_compliance_results.csv
- results/format_compliance_summary.txt
"""

import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DEFAULT_LLM_MODEL
from src.query_classifier import classify_query

from .persona_evaluation import run_persona_evaluation

# ---------------------------------------------------------------------------
# Format rules
# Each entry: condition_key, condition_value, pattern, flags, description
# ---------------------------------------------------------------------------

FORMAT_RULES: dict[str, dict] = {
    "procedure_has_numbered_steps": {
        "condition_key": "query_type",
        "condition_value": "procedure",
        "pattern": r"^\s*\d+[\.\)]\s+\w",
        "flags": re.MULTILINE,
        "description": "Procedure response uses numbered steps",
    },
    "comparison_has_table": {
        "condition_key": "query_type",
        "condition_value": "comparison",
        "pattern": r"\|.+\|.+\|",
        "flags": 0,
        "description": "Comparison response includes a markdown table",
    },
    "eligibility_has_inclusion": {
        "condition_key": "query_type",
        "condition_value": "eligibility",
        "pattern": r"inclusion|include|eligible",
        "flags": re.IGNORECASE,
        "description": "Eligibility response mentions inclusion criteria",
    },
    "eligibility_has_exclusion": {
        "condition_key": "query_type",
        "condition_value": "eligibility",
        "pattern": r"exclusion|exclude|ineligible",
        "flags": re.IGNORECASE,
        "description": "Eligibility response mentions exclusion criteria",
    },
    "numerical_leads_with_number": {
        "condition_key": "query_type",
        "condition_value": "numerical",
        "pattern": r"^[\w\s]{0,60}?\d+",
        "flags": 0,
        "description": "Numerical response leads with a number",
    },
    "timeline_contains_timeframe": {
        "condition_key": "query_type",
        "condition_value": "timeline",
        "pattern": r"\b\d+\s*(day|week|month|year)s?\b",
        "flags": re.IGNORECASE,
        "description": "Timeline response contains explicit timeframe",
    },
    "safety_contains_severity": {
        "condition_key": "query_type",
        "condition_value": "safety",
        "pattern": r"\b(grade\s*[1-5]|mild|moderate|severe|serious)\b",
        "flags": re.IGNORECASE,
        "description": "Safety response mentions severity classification",
    },
    "compliance_cites_regulation": {
        "condition_key": "query_type",
        "condition_value": "compliance",
        "pattern": r"\b(FDA|EMA|ICH|GCP|21\s*CFR|ICH-GCP)\b",
        "flags": re.IGNORECASE,
        "description": "Compliance response cites a regulation",
    },
    "novice_has_bullet_points": {
        "condition_key": "persona",
        "condition_value": "novice",
        "pattern": r"^\s*[-•*]\s+\w",
        "flags": re.MULTILINE,
        "description": "Novice response uses bullet points",
    },
    "novice_has_key_takeaway": {
        "condition_key": "persona",
        "condition_value": "novice",
        "pattern": r"key\s+takeaway|📌",
        "flags": re.IGNORECASE,
        "description": "Novice response includes a key takeaway",
    },
    "novice_defines_terms": {
        "condition_key": "persona",
        "condition_value": "novice",
        "pattern": r"\(.{3,60}\)",
        "flags": 0,
        "description": "Novice response defines terms in parentheses",
    },
    "executive_has_summary": {
        "condition_key": "persona",
        "condition_value": "executive",
        "pattern": r"executive\s+summary|in\s+brief|key\s+point",
        "flags": re.IGNORECASE,
        "description": "Executive response includes a summary section",
    },
    "executive_has_recommendation": {
        "condition_key": "persona",
        "condition_value": "executive",
        "pattern": r"recommend|next\s+step|action\s+item|decision",
        "flags": re.IGNORECASE,
        "description": "Executive response includes recommendation or next step",
    },
    "expert_uses_technical_terms": {
        "condition_key": "persona",
        "condition_value": "expert",
        "pattern": r"\b(RECIST|ICH.GCP|21\s*CFR|SUVmax|iRECIST|CTCAE)\b",
        "flags": re.IGNORECASE,
        "description": "Expert response uses domain-specific technical terms",
    },
    "regulatory_cites_standard": {
        "condition_key": "persona",
        "condition_value": "regulatory",
        "pattern": r"\b(FDA|EMA|ICH|GCP|CFR|guidance|compliance|audit)\b",
        "flags": re.IGNORECASE,
        "description": "Regulatory response cites a standard or guidance",
    },
    "intermediate_has_example": {
        "condition_key": "persona",
        "condition_value": "intermediate",
        "pattern": r"\bfor\s+example\b|\be\.g\.\b|\bsuch\s+as\b",
        "flags": re.IGNORECASE,
        "description": "Intermediate response includes a concrete example",
    },
}


def check_rule(rule_name: str, text: str, query_type: str, persona: str) -> bool | None:
    """
    Check whether a single format rule passes for the given response.

    Returns True/False when the rule is applicable, None when not applicable.

    Args:
        rule_name: Key in FORMAT_RULES.
        text: Response text to check.
        query_type: Classified query type string.
        persona: Persona string (e.g. "novice").

    Returns:
        True if rule passes, False if it fails, None if not applicable.
    """
    rule = FORMAT_RULES.get(rule_name)
    if rule is None:
        return None

    condition_key = rule["condition_key"]
    condition_value = rule["condition_value"]

    # Determine applicability
    if condition_key == "query_type" and query_type != condition_value:
        return None
    if condition_key == "persona" and persona != condition_value:
        return None

    return bool(re.search(rule["pattern"], text, rule["flags"]))


def compute_compliance_score(text: str, query_type: str, persona: str) -> float:
    """
    Compute the compliance score for a single response.

    Score = passed_applicable_rules / total_applicable_rules.
    Returns 0.0 when no rules are applicable.

    Args:
        text: Response text.
        query_type: Classified query type string.
        persona: Persona string.

    Returns:
        Float in [0.0, 1.0].
    """
    applicable = []
    for rule_name in FORMAT_RULES:
        result = check_rule(rule_name, text, query_type, persona)
        if result is not None:
            applicable.append(result)

    if not applicable:
        return 0.0

    return sum(applicable) / len(applicable)


# Re-export for use in adaptive_vs_generic
__all__ = ["check_rule", "compute_compliance_score", "run_format_compliance", "FORMAT_RULES"]


def run_format_compliance(
    document_path: str,
    queries: list[str] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    llm_model: str = DEFAULT_LLM_MODEL,
    output_dir: str = "results",
) -> pd.DataFrame:
    """
    Evaluate format compliance for each (persona, query) pair.

    Reads persona_responses.json if it already exists to avoid redundant
    LLM calls. Generates responses from scratch otherwise.

    Args:
        document_path: Path to the source PDF document.
        queries: Optional list of test queries.
        embedding_model: Embedding model identifier.
        llm_model: LLM model identifier.
        output_dir: Directory for output files.

    Returns:
        DataFrame with one row per (query, persona), one bool column per rule,
        plus applicable_rules_count, passed_rules_count, and compliance_score.
    """
    os.makedirs(output_dir, exist_ok=True)

    persona_json_path = os.path.join(output_dir, "persona_responses.json")

    if os.path.exists(persona_json_path):
        print(f"[REUSE] Loading existing persona responses from {persona_json_path}")
        with open(persona_json_path, encoding="utf-8") as f:
            persona_data = json.load(f)
    else:
        print("[GEN] persona_responses.json not found — generating responses now")
        persona_data = run_persona_evaluation(
            document_path=document_path,
            queries=queries,
            embedding_model=embedding_model,
            llm_model=llm_model,
            output_dir=output_dir,
        )

    rows = []
    rule_names = list(FORMAT_RULES.keys())

    for entry in persona_data:
        query = entry["query"]
        query_type = entry.get("query_type", classify_query(query).value)

        for persona, data in entry["responses"].items():
            text = data.get("response", "")

            rule_results = {}
            applicable_count = 0
            passed_count = 0

            for rule_name in rule_names:
                result = check_rule(rule_name, text, query_type, persona)
                rule_results[rule_name] = result
                if result is not None:
                    applicable_count += 1
                    if result:
                        passed_count += 1

            compliance = passed_count / applicable_count if applicable_count else 0.0

            row = {
                "query": query,
                "persona": persona,
                "query_type": query_type,
                **rule_results,
                "applicable_rules_count": applicable_count,
                "passed_rules_count": passed_count,
                "compliance_score": round(compliance, 3),
            }
            rows.append(row)

    df = pd.DataFrame(rows)

    csv_path = os.path.join(output_dir, "format_compliance_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"[SAVED] {csv_path}")

    summary_path = os.path.join(output_dir, "format_compliance_summary.txt")
    _write_summary(df, summary_path)
    print(f"[SAVED] {summary_path}")

    return df


def _write_summary(df: pd.DataFrame, output_path: str) -> None:
    """Write a human-readable compliance summary report."""
    rule_names = list(FORMAT_RULES.keys())

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("        FORMAT COMPLIANCE EVALUATION REPORT\n")
        f.write("=" * 70 + "\n\n")

        overall = df["compliance_score"].mean()
        f.write(f"Overall Compliance Score: {overall:.1%}\n\n")

        # Per-persona compliance
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  PER-PERSONA COMPLIANCE" + " " * 44 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(f"{'Persona':<15} {'Avg Score':<12} {'Applicable':<12} {'Passed':<10}\n")
        f.write("-" * 55 + "\n")

        persona_order = ["novice", "intermediate", "expert", "regulatory", "executive"]
        for persona in persona_order:
            pdata = df[df["persona"] == persona]
            if pdata.empty:
                continue
            avg_score = pdata["compliance_score"].mean()
            avg_applicable = pdata["applicable_rules_count"].mean()
            avg_passed = pdata["passed_rules_count"].mean()
            f.write(
                f"{persona.title():<15} {avg_score:<12.1%} {avg_applicable:<12.1f} {avg_passed:<10.1f}\n"
            )

        f.write("\n")

        # Per-query-type compliance
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  PER-QUERY-TYPE COMPLIANCE" + " " * 41 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(f"{'Query Type':<20} {'Avg Score':<12}\n")
        f.write("-" * 35 + "\n")

        for qtype in sorted(df["query_type"].unique()):
            qdata = df[df["query_type"] == qtype]
            avg_score = qdata["compliance_score"].mean()
            f.write(f"{qtype.title():<20} {avg_score:<12.1%}\n")

        f.write("\n")

        # Per-rule pass rate
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  PER-RULE PASS RATE" + " " * 48 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(f"{'Rule':<45} {'Pass Rate':<12} {'Applicable':<10}\n")
        f.write("-" * 70 + "\n")

        for rule_name in rule_names:
            if rule_name not in df.columns:
                continue
            applicable = df[rule_name].notna().sum()
            if applicable == 0:
                continue
            passed = df[rule_name].sum()
            pass_rate = passed / applicable if applicable else 0.0
            f.write(f"{rule_name:<45} {pass_rate:<12.1%} {applicable:<10}\n")

        f.write("\n")
        f.write("=" * 70 + "\n")
        f.write("                          END OF REPORT\n")
        f.write("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run format compliance evaluation")
    parser.add_argument("--document", type=str, required=True)
    parser.add_argument("--output", type=str, default="results")
    parser.add_argument("--model", type=str, default="S-PubMedBert-MS-MARCO")
    args = parser.parse_args()

    run_format_compliance(
        document_path=args.document,
        embedding_model=args.model,
        output_dir=args.output,
    )
