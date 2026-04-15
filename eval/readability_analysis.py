"""
Readability Analysis Evaluation
================================

Proves that NOVICE responses are measurably simpler than EXPERT responses.

Reads persona_responses.json if present (zero LLM calls).
Generates responses fresh if the file is absent.

Requires: textstat  (conda install -c conda-forge textstat)

Output:
- results/readability_analysis_results.csv
- results/readability_analysis_summary.txt
"""

import json
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import textstat
except ImportError as exc:
    raise ImportError(
        "textstat is required for readability analysis. "
        "Install with: conda install -c conda-forge textstat"
    ) from exc

from src.config import DEFAULT_LLM_MODEL
from src.query_classifier import classify_query

# Reuse persona evaluation infrastructure
from .adaptive_vs_generic import PERSONA_GRADE_TARGETS
from .persona_evaluation import run_persona_evaluation

DEFAULT_QUERIES = [
    "What is RECIST 1.1?",
    "How do I measure target lesions?",
    "What are the compliance requirements for imaging?",
    "Compare CT and MRI for tumor assessment",
    "What is the imaging schedule?",
]


def compute_readability_metrics(text: str) -> dict:
    """
    Compute a suite of readability metrics for a text string.

    Args:
        text: The response text to analyse.

    Returns:
        Dict with keys: flesch_reading_ease, flesch_kincaid_grade,
        gunning_fog, word_count, sentence_count, difficult_words,
        avg_sentence_length.
    """
    if not text or not text.strip():
        return {
            "flesch_reading_ease": 0.0,
            "flesch_kincaid_grade": 0.0,
            "gunning_fog": 0.0,
            "word_count": 0,
            "sentence_count": 0,
            "difficult_words": 0,
            "avg_sentence_length": 0.0,
        }

    word_count = len(text.split())
    sentence_count = textstat.sentence_count(text)
    avg_sentence_length = word_count / max(sentence_count, 1)

    return {
        "flesch_reading_ease": round(textstat.flesch_reading_ease(text), 2),
        "flesch_kincaid_grade": round(textstat.flesch_kincaid_grade(text), 2),
        "gunning_fog": round(textstat.gunning_fog(text), 2),
        "word_count": word_count,
        "sentence_count": sentence_count,
        "difficult_words": textstat.difficult_words(text),
        "avg_sentence_length": round(avg_sentence_length, 2),
    }


def run_readability_analysis(
    document_path: str,
    queries: list[str] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    llm_model: str = DEFAULT_LLM_MODEL,
    output_dir: str = "results",
) -> pd.DataFrame:
    """
    Compute readability metrics for each persona's responses.

    Reads persona_responses.json if it already exists to avoid redundant
    LLM calls. Generates responses from scratch otherwise.

    Args:
        document_path: Path to the source PDF document.
        queries: Optional list of test queries.
        embedding_model: Embedding model identifier.
        llm_model: LLM model identifier.
        output_dir: Directory for output files.

    Returns:
        DataFrame with one row per (query, persona).
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
            queries=queries or DEFAULT_QUERIES,
            embedding_model=embedding_model,
            llm_model=llm_model,
            output_dir=output_dir,
        )

    rows = []
    for entry in persona_data:
        query = entry["query"]
        query_type = entry.get("query_type", classify_query(query).value)

        for persona, data in entry["responses"].items():
            text = data.get("response", "")
            metrics = compute_readability_metrics(text)
            rows.append(
                {
                    "query": query,
                    "persona": persona,
                    "query_type": query_type,
                    **metrics,
                }
            )

    df = pd.DataFrame(rows)

    # Save results
    csv_path = os.path.join(output_dir, "readability_analysis_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"[SAVED] {csv_path}")

    summary_path = os.path.join(output_dir, "readability_analysis_summary.txt")
    _write_summary(df, summary_path)
    print(f"[SAVED] {summary_path}")

    return df


def _write_summary(df: pd.DataFrame, output_path: str) -> None:
    """Write a human-readable readability summary."""
    persona_order = ["novice", "intermediate", "expert", "regulatory", "executive"]

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("        READABILITY ANALYSIS REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write("+" + "-" * 68 + "+\n")
        f.write("|  AVERAGE METRICS PER PERSONA" + " " * 39 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")

        f.write(
            f"{'Persona':<15} {'Flesch Ease':<14} {'FK Grade':<12} "
            f"{'Gunning Fog':<14} {'Avg Words':<10}\n"
        )
        f.write("-" * 70 + "\n")

        for persona in persona_order:
            pdata = df[df["persona"] == persona]
            if pdata.empty:
                continue
            ease = pdata["flesch_reading_ease"].mean()
            grade = pdata["flesch_kincaid_grade"].mean()
            fog = pdata["gunning_fog"].mean()
            words = pdata["word_count"].mean()
            f.write(
                f"{persona.title():<15} {ease:<14.1f} {grade:<12.1f} {fog:<14.1f} {words:<10.0f}\n"
            )

        f.write("\n")

        # Headline finding
        novice_grade = df[df["persona"] == "novice"]["flesch_kincaid_grade"].mean()
        expert_grade = df[df["persona"] == "expert"]["flesch_kincaid_grade"].mean()

        if novice_grade < expert_grade:
            result_symbol = "[PASS]"
            result_text = (
                f"NOVICE responses are measurably simpler than EXPERT "
                f"(FK Grade {novice_grade:.1f} vs {expert_grade:.1f})"
            )
        else:
            result_symbol = "[FAIL]"
            result_text = (
                f"No significant readability difference detected "
                f"(Novice FK={novice_grade:.1f}, Expert FK={expert_grade:.1f})"
            )

        f.write(f"\n{result_symbol} {result_text}\n\n")

        # Rank order by reading ease (higher = simpler)
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  RANK ORDER BY READING EASE (higher = simpler)" + " " * 21 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")

        ranked = df.groupby("persona")["flesch_reading_ease"].mean().sort_values(ascending=False)
        for rank, (persona, ease) in enumerate(ranked.items(), 1):
            f.write(f"  {rank}. {persona.title():<15} Flesch Ease: {ease:.1f}\n")

        f.write("\n")

        # Per-persona FK grade target comparison
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  FK GRADE TARGET COMPARISON (PERSONA_GRADE_TARGETS)" + " " * 16 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(f"{'Persona':<15} {'FK Grade (avg)':<16} {'Target Range':<16} {'Status':<10}\n")
        f.write("-" * 60 + "\n")

        for persona in persona_order:
            pdata = df[df["persona"] == persona]
            if pdata.empty:
                continue
            avg_grade = pdata["flesch_kincaid_grade"].mean()
            target = PERSONA_GRADE_TARGETS.get(persona)
            if target is None:
                status = "N/A"
                target_str = "—"
            else:
                target_str = f"({target[0]:.0f}, {target[1]:.0f})"
                status = "PASS" if target[0] <= avg_grade <= target[1] else "FAIL"
            f.write(f"{persona.title():<15} {avg_grade:<16.1f} {target_str:<16} {status:<10}\n")

        f.write("\n")
        f.write("=" * 70 + "\n")
        f.write("                          END OF REPORT\n")
        f.write("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run readability analysis")
    parser.add_argument("--document", type=str, required=True)
    parser.add_argument("--output", type=str, default="results")
    parser.add_argument("--model", type=str, default="S-PubMedBert-MS-MARCO")
    args = parser.parse_args()

    run_readability_analysis(
        document_path=args.document,
        embedding_model=args.model,
        output_dir=args.output,
    )
