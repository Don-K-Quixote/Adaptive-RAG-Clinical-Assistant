"""
Evaluation Metrics Calculation
==============================

Aggregates and calculates summary metrics from all evaluation runs.

Reads:
- results/model_comparison_results.csv
- results/hybrid_vs_semantic_comparison.csv
- results/latency_results.csv
- results/persona_responses.json

Output:
- results/final_metrics_summary.txt
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd


def load_results(results_dir: str = "results") -> dict:
    """Load all evaluation result files."""
    results = {}

    # Model comparison
    model_path = os.path.join(results_dir, "model_comparison_results.csv")
    if os.path.exists(model_path):
        results["model_comparison"] = pd.read_csv(model_path)
        print(f"✅ Loaded: {model_path}")

    # Hybrid comparison
    hybrid_path = os.path.join(results_dir, "hybrid_vs_semantic_comparison.csv")
    if os.path.exists(hybrid_path):
        results["hybrid_comparison"] = pd.read_csv(hybrid_path)
        print(f"✅ Loaded: {hybrid_path}")

    # Latency results
    latency_path = os.path.join(results_dir, "latency_results.csv")
    if os.path.exists(latency_path):
        results["latency"] = pd.read_csv(latency_path)
        print(f"✅ Loaded: {latency_path}")

    # Persona responses
    persona_path = os.path.join(results_dir, "persona_responses.json")
    if os.path.exists(persona_path):
        with open(persona_path, encoding="utf-8") as f:
            results["persona_responses"] = json.load(f)
        print(f"✅ Loaded: {persona_path}")

    # Classification accuracy
    classify_path = os.path.join(results_dir, "classification_accuracy_results.csv")
    if os.path.exists(classify_path):
        results["classification_accuracy"] = pd.read_csv(classify_path)
        print(f"✅ Loaded: {classify_path}")

    # Readability analysis
    readability_path = os.path.join(results_dir, "readability_analysis_results.csv")
    if os.path.exists(readability_path):
        results["readability"] = pd.read_csv(readability_path)
        print(f"✅ Loaded: {readability_path}")

    # Format compliance
    compliance_path = os.path.join(results_dir, "format_compliance_results.csv")
    if os.path.exists(compliance_path):
        results["compliance"] = pd.read_csv(compliance_path)
        print(f"✅ Loaded: {compliance_path}")

    # Adaptive vs generic
    avsg_path = os.path.join(results_dir, "adaptive_vs_generic_results.csv")
    if os.path.exists(avsg_path):
        results["adaptive_vs_generic"] = pd.read_csv(avsg_path)
        print(f"✅ Loaded: {avsg_path}")

    return results


def calculate_model_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for model comparison."""
    metrics = {}

    for model in df["model"].unique():
        model_df = df[df["model"] == model]
        metrics[model] = {
            "avg_retrieval_ms": model_df["retrieval_time_ms"].mean(),
            "std_retrieval_ms": model_df["retrieval_time_ms"].std(),
            "avg_diversity": model_df["diversity_score"].mean(),
            "model_type": model_df["model_type"].iloc[0],
        }

    # Find best performers
    best_speed = min(metrics, key=lambda x: metrics[x]["avg_retrieval_ms"])
    best_diversity = max(metrics, key=lambda x: metrics[x]["avg_diversity"])

    return {
        "models": metrics,
        "best_speed": best_speed,
        "best_diversity": best_diversity,
    }


def calculate_hybrid_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for hybrid comparison."""
    return {
        "hybrid_avg_time_ms": df["hybrid_time_ms"].mean(),
        "semantic_avg_time_ms": df["semantic_time_ms"].mean(),
        "hybrid_avg_diversity": df["hybrid_diversity"].mean(),
        "semantic_avg_diversity": df["semantic_diversity"].mean(),
        "avg_diversity_improvement": df["diversity_improvement"].mean(),
        "avg_time_overhead_ms": df["time_overhead_ms"].mean(),
        "pct_improved": (df["diversity_improvement"] > 0).mean() * 100,
    }


def calculate_latency_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary latency metrics."""
    return {
        "avg_retrieval_ms": df["retrieval_mean_ms"].mean(),
        "avg_generation_ms": df["generation_mean_ms"].mean(),
        "avg_total_ms": df["total_mean_ms"].mean(),
        "p50_total_ms": df["total_mean_ms"].median(),
        "p95_total_ms": df["total_mean_ms"].quantile(0.95),
        "max_total_ms": df["total_mean_ms"].max(),
    }


def calculate_persona_metrics(data: list) -> dict:
    """Calculate summary metrics for persona responses."""
    persona_stats = {}

    for persona in ["novice", "intermediate", "expert", "regulatory", "executive"]:
        word_counts = []
        gen_times = []

        for query_result in data:
            if persona in query_result["responses"]:
                resp = query_result["responses"][persona]
                word_counts.append(resp["word_count"])
                gen_times.append(resp["generation_time_ms"])

        if word_counts:
            persona_stats[persona] = {
                "avg_word_count": np.mean(word_counts),
                "avg_generation_ms": np.mean(gen_times),
                "min_word_count": np.min(word_counts),
                "max_word_count": np.max(word_counts),
            }

    return persona_stats


def calculate_classification_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for query classification accuracy."""
    overall_accuracy = df["is_correct"].mean()
    avg_confidence = df["confidence"].mean()

    per_type_accuracy = {}
    for qtype in df["expected_type"].unique():
        type_df = df[df["expected_type"] == qtype]
        per_type_accuracy[qtype] = type_df["is_correct"].mean()

    return {
        "overall_accuracy": overall_accuracy,
        "per_type_accuracy": per_type_accuracy,
        "avg_confidence": avg_confidence,
        "total_queries": len(df),
        "correct_count": int(df["is_correct"].sum()),
    }


def calculate_readability_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for readability analysis."""
    persona_flesch_ease = df.groupby("persona")["flesch_reading_ease"].mean().to_dict()
    persona_fk_grade = df.groupby("persona")["flesch_kincaid_grade"].mean().to_dict()

    novice_grade = persona_fk_grade.get("novice", 99.0)
    expert_grade = persona_fk_grade.get("expert", 0.0)

    return {
        "per_persona_flesch_ease": persona_flesch_ease,
        "per_persona_fk_grade": persona_fk_grade,
        "novice_easier_than_expert": novice_grade < expert_grade,
        "novice_fk_grade": novice_grade,
        "expert_fk_grade": expert_grade,
    }


def calculate_compliance_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for format compliance evaluation."""
    per_persona_compliance = df.groupby("persona")["compliance_score"].mean().to_dict()
    per_query_type_compliance = df.groupby("query_type")["compliance_score"].mean().to_dict()
    overall_compliance = df["compliance_score"].mean()

    return {
        "overall_compliance": overall_compliance,
        "per_persona_compliance": per_persona_compliance,
        "per_query_type_compliance": per_query_type_compliance,
    }


def calculate_adaptive_vs_generic_metrics(df: pd.DataFrame) -> dict:
    """Calculate summary metrics for adaptive vs generic comparison."""
    adaptive_win_rate = df["adaptive_overall_wins"].mean()
    compliance_delta = df["compliance_delta"].mean()
    adaptive_readability_fit_pct = df["persona_appropriate_readability"].mean()

    per_persona_win_rate = df.groupby("persona")["adaptive_overall_wins"].mean().to_dict()

    return {
        "adaptive_win_rate": adaptive_win_rate,
        "compliance_delta": compliance_delta,
        "adaptive_readability_fit_pct": adaptive_readability_fit_pct,
        "per_persona_win_rate": per_persona_win_rate,
        "total_queries": len(df),
        "adaptive_wins_count": int(df["adaptive_overall_wins"].sum()),
    }


def calculate_all_metrics(results_dir: str = "results") -> dict:
    """
    Calculate all evaluation metrics and generate summary report.

    Args:
        results_dir: Directory containing evaluation results

    Returns:
        Dictionary with all calculated metrics
    """
    print(f"\n📊 Loading evaluation results from {results_dir}...\n")

    results = load_results(results_dir)

    if not results:
        print("❌ No results found!")
        return {}

    all_metrics = {}

    # Model comparison metrics
    if "model_comparison" in results:
        all_metrics["model_comparison"] = calculate_model_metrics(results["model_comparison"])

    # Hybrid comparison metrics
    if "hybrid_comparison" in results:
        all_metrics["hybrid_comparison"] = calculate_hybrid_metrics(results["hybrid_comparison"])

    # Latency metrics
    if "latency" in results:
        all_metrics["latency"] = calculate_latency_metrics(results["latency"])

    # Persona metrics
    if "persona_responses" in results:
        all_metrics["persona"] = calculate_persona_metrics(results["persona_responses"])

    # Classification accuracy metrics
    if "classification_accuracy" in results:
        all_metrics["classification"] = calculate_classification_metrics(
            results["classification_accuracy"]
        )

    # Readability metrics
    if "readability" in results:
        all_metrics["readability"] = calculate_readability_metrics(results["readability"])

    # Format compliance metrics
    if "compliance" in results:
        all_metrics["compliance"] = calculate_compliance_metrics(results["compliance"])

    # Adaptive vs generic metrics
    if "adaptive_vs_generic" in results:
        all_metrics["adaptive_vs_generic"] = calculate_adaptive_vs_generic_metrics(
            results["adaptive_vs_generic"]
        )

    # Generate summary report
    summary_path = os.path.join(results_dir, "final_metrics_summary.txt")
    generate_summary_report(all_metrics, summary_path)

    return all_metrics


def generate_summary_report(metrics: dict, output_path: str):
    """Generate a comprehensive summary report."""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("        ADAPTIVE RAG CLINICAL ASSISTANT - EVALUATION SUMMARY\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # Model comparison
        if "model_comparison" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  EMBEDDING MODEL COMPARISON" + " " * 40 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            mc = metrics["model_comparison"]

            f.write(f"{'Model':<35} {'Type':<12} {'Avg Time':<12} {'Diversity':<10}\n")
            f.write("-" * 70 + "\n")

            for model, stats in mc["models"].items():
                f.write(
                    f"{model:<35} {stats['model_type']:<12} "
                    f"{stats['avg_retrieval_ms']:.2f}ms{'':<5} "
                    f"{stats['avg_diversity']:.3f}\n"
                )

            f.write("\n")
            f.write(f"[BEST] Fastest: {mc['best_speed']}\n")
            f.write(f"[BEST] Most Diverse: {mc['best_diversity']}\n\n")

        # Hybrid comparison
        if "hybrid_comparison" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  HYBRID (RRF) VS SEMANTIC RETRIEVAL" + " " * 31 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            hc = metrics["hybrid_comparison"]

            f.write(f"{'Metric':<35} {'Hybrid':<15} {'Semantic':<15}\n")
            f.write("-" * 70 + "\n")
            f.write(
                f"{'Avg Retrieval Time':<35} {hc['hybrid_avg_time_ms']:.2f}ms{'':<8} "
                f"{hc['semantic_avg_time_ms']:.2f}ms\n"
            )
            f.write(
                f"{'Avg Diversity Score':<35} {hc['hybrid_avg_diversity']:.3f}{'':<10} "
                f"{hc['semantic_avg_diversity']:.3f}\n"
            )
            f.write("\n")
            f.write(
                f"Diversity Improvement: {hc['avg_diversity_improvement']:+.3f} "
                f"({hc['pct_improved']:.0f}% of queries improved)\n"
            )
            f.write(f"Time Overhead: +{hc['avg_time_overhead_ms']:.2f}ms\n\n")

        # Latency
        if "latency" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  END-TO-END LATENCY" + " " * 48 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            lat = metrics["latency"]

            f.write(f"Retrieval:     {lat['avg_retrieval_ms']:.2f}ms avg\n")
            f.write(f"Generation:    {lat['avg_generation_ms']:.2f}ms avg\n")
            f.write(f"Total:         {lat['avg_total_ms']:.2f}ms avg\n")
            f.write(f"P50:           {lat['p50_total_ms']:.2f}ms\n")
            f.write(f"P95:           {lat['p95_total_ms']:.2f}ms\n")
            f.write(f"Max:           {lat['max_total_ms']:.2f}ms\n\n")

        # Persona
        if "persona" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  PERSONA RESPONSE CHARACTERISTICS" + " " * 33 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            f.write(
                f"{'Persona':<15} {'Avg Words':<12} {'Min':<8} {'Max':<8} {'Avg Gen Time':<12}\n"
            )
            f.write("-" * 70 + "\n")

            for persona, stats in metrics["persona"].items():
                f.write(
                    f"{persona.title():<15} {stats['avg_word_count']:.0f}{'':<9} "
                    f"{stats['min_word_count']:<8} {stats['max_word_count']:<8} "
                    f"{stats['avg_generation_ms']:.0f}ms\n"
                )

            f.write("\n")

        # Classification accuracy
        if "classification" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  QUERY CLASSIFICATION ACCURACY" + " " * 37 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            cl = metrics["classification"]
            f.write(
                f"Overall Accuracy: {cl['overall_accuracy']:.1%}  "
                f"({cl['correct_count']}/{cl['total_queries']} correct)\n"
            )
            f.write(f"Avg Confidence:   {cl['avg_confidence']:.3f}\n\n")

            f.write(f"{'Query Type':<20} {'Accuracy':<10}\n")
            f.write("-" * 35 + "\n")
            for qtype, acc in sorted(cl["per_type_accuracy"].items()):
                f.write(f"{qtype:<20} {acc:.1%}\n")
            f.write("\n")

        # Readability analysis
        if "readability" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  READABILITY ANALYSIS" + " " * 46 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            rd = metrics["readability"]
            f.write(f"{'Persona':<15} {'Flesch Ease':<14} {'FK Grade':<12}\n")
            f.write("-" * 45 + "\n")
            persona_order = ["novice", "intermediate", "expert", "regulatory", "executive"]
            for persona in persona_order:
                ease = rd["per_persona_flesch_ease"].get(persona, 0.0)
                grade = rd["per_persona_fk_grade"].get(persona, 0.0)
                f.write(f"{persona.title():<15} {ease:<14.1f} {grade:<12.1f}\n")

            symbol = "[PASS]" if rd["novice_easier_than_expert"] else "[FAIL]"
            f.write(
                f"\n{symbol} Novice FK Grade ({rd['novice_fk_grade']:.1f}) vs "
                f"Expert FK Grade ({rd['expert_fk_grade']:.1f})\n\n"
            )

        # Format compliance
        if "compliance" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  FORMAT COMPLIANCE" + " " * 49 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            cp = metrics["compliance"]
            f.write(f"Overall Compliance: {cp['overall_compliance']:.1%}\n\n")
            f.write(f"{'Persona':<15} {'Compliance':<12}\n")
            f.write("-" * 30 + "\n")
            persona_order = ["novice", "intermediate", "expert", "regulatory", "executive"]
            for persona in persona_order:
                score = cp["per_persona_compliance"].get(persona, 0.0)
                f.write(f"{persona.title():<15} {score:.1%}\n")
            f.write("\n")

        # Adaptive vs generic
        if "adaptive_vs_generic" in metrics:
            f.write("+" + "-" * 68 + "+\n")
            f.write("|  ADAPTIVE vs GENERIC RAG" + " " * 43 + "|\n")
            f.write("+" + "-" * 68 + "+\n\n")

            av = metrics["adaptive_vs_generic"]
            f.write(
                f"Adaptive Win Rate:     {av['adaptive_win_rate']:.1%}  "
                f"({av['adaptive_wins_count']}/{av['total_queries']} queries)\n"
            )
            f.write(f"Avg Compliance Delta:  {av['compliance_delta']:+.3f}\n")
            f.write(f"Readability Fit:       {av['adaptive_readability_fit_pct']:.1%}\n\n")
            f.write(f"{'Persona':<15} {'Win Rate':<10}\n")
            f.write("-" * 28 + "\n")
            persona_order = ["novice", "intermediate", "expert", "regulatory", "executive"]
            for persona in persona_order:
                wr = av["per_persona_win_rate"].get(persona, 0.0)
                f.write(f"{persona.title():<15} {wr:.1%}\n")
            f.write("\n")

        f.write("=" * 70 + "\n")
        f.write("                          END OF REPORT\n")
        f.write("=" * 70 + "\n")

    print(f"\n[SAVED] {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calculate evaluation metrics")
    parser.add_argument("--results", type=str, default="results", help="Results directory")

    args = parser.parse_args()

    calculate_all_metrics(results_dir=args.results)
