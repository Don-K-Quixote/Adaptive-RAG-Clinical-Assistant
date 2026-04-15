"""
Evaluation Runner - Entry Point
================================

Unified entry point for all evaluation scripts.
Similar to how app.py is the entry point for the main application,
run_eval.py is the entry point for evaluation.

Usage:
    # Run all evaluations
    python run_eval.py --document path/to/irc.pdf --all

    # Run specific evaluations
    python run_eval.py --document path/to/irc.pdf --models
    python run_eval.py --document path/to/irc.pdf --hybrid
    python run_eval.py --document path/to/irc.pdf --personas
    python run_eval.py --document path/to/irc.pdf --latency

    # Calculate metrics from existing results
    python run_eval.py --metrics

    # Custom output directory
    python run_eval.py --document irc.pdf --all --output my_results/
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from eval.adaptive_vs_generic import run_adaptive_vs_generic
from eval.classification_accuracy import run_classification_accuracy
from eval.format_compliance import run_format_compliance
from eval.hybrid_comparison import run_hybrid_comparison
from eval.latency_measurement import run_latency_measurement
from eval.metrics import calculate_all_metrics
from eval.model_comparison import run_model_comparison
from eval.persona_evaluation import run_persona_evaluation
from eval.readability_analysis import run_readability_analysis


def print_banner():
    """Print a nice banner."""
    print("\n" + "=" * 70)
    print("     🧪 ADAPTIVE RAG CLINICAL ASSISTANT - EVALUATION SUITE")
    print("=" * 70)
    print(f"     Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")


def print_section(title: str):
    """Print a section header."""
    print("\n" + "─" * 70)
    print(f"  📊 {title}")
    print("─" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluation Suite for Adaptive RAG Clinical Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_eval.py --document irc.pdf --all
  python run_eval.py --document irc.pdf --models --hybrid
  python run_eval.py --metrics
        """,
    )

    # Document input
    parser.add_argument("--document", "-d", type=str, help="Path to PDF document for evaluation")

    # Evaluation types
    parser.add_argument("--all", "-a", action="store_true", help="Run all evaluations")
    parser.add_argument(
        "--models", "-m", action="store_true", help="Run embedding model comparison"
    )
    parser.add_argument(
        "--hybrid", "-H", action="store_true", help="Run hybrid vs semantic comparison"
    )
    parser.add_argument(
        "--personas", "-p", action="store_true", help="Run persona-based evaluation"
    )
    parser.add_argument("--latency", "-l", action="store_true", help="Run latency measurement")
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Calculate metrics from existing results (no document needed)",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Run query classification accuracy evaluation (no document needed)",
    )
    parser.add_argument(
        "--readability",
        action="store_true",
        help="Run readability analysis per persona (requires --document)",
    )
    parser.add_argument(
        "--compliance",
        action="store_true",
        help="Run format compliance evaluation (requires --document)",
    )
    parser.add_argument(
        "--adaptive-vs-generic",
        dest="adaptive",
        action="store_true",
        help="Run head-to-head adaptive vs generic RAG comparison (requires --document)",
    )

    # Configuration
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="results",
        help="Output directory for results (default: results)",
    )
    parser.add_argument(
        "--embedding-model",
        "-e",
        type=str,
        default="S-PubMedBert-MS-MARCO",
        help="Embedding model to use (default: S-PubMedBert-MS-MARCO)",
    )
    parser.add_argument(
        "--runs",
        "-r",
        type=int,
        default=3,
        help="Number of runs for latency averaging (default: 3)",
    )

    args = parser.parse_args()

    # Validate arguments
    if args.metrics:
        # Metrics calculation doesn't need a document
        print_banner()
        print_section("CALCULATING METRICS FROM EXISTING RESULTS")
        calculate_all_metrics(results_dir=args.output)
        print("\n✅ Metrics calculation complete!")
        return

    # Determine which evaluations to run
    run_all = args.all
    run_models = args.models or run_all
    run_hybrid = args.hybrid or run_all
    run_personas = args.personas or run_all
    run_latency = args.latency or run_all
    run_classify = args.classify or run_all
    run_readability = args.readability or run_all
    run_compliance = args.compliance or run_all
    run_adaptive = args.adaptive or run_all

    # --classify does not require a document; all others do
    needs_document = any(
        [
            run_models,
            run_hybrid,
            run_personas,
            run_latency,
            run_readability,
            run_compliance,
            run_adaptive,
        ]
    )

    if not args.document and needs_document:
        parser.error("--document is required for the selected evaluations")

    if args.document and not os.path.exists(args.document):
        parser.error(f"Document not found: {args.document}")

    if not any(
        [
            run_models,
            run_hybrid,
            run_personas,
            run_latency,
            run_classify,
            run_readability,
            run_compliance,
            run_adaptive,
        ]
    ):
        parser.error(
            "Please specify at least one evaluation type "
            "(--all, --models, --hybrid, --personas, --latency, "
            "--classify, --readability, --compliance, --adaptive-vs-generic)"
        )

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    # Print banner
    print_banner()

    print(f"📄 Document: {args.document}")
    print(f"📁 Output:   {args.output}")
    print(f"🔤 Model:    {args.embedding_model}")
    print()

    evaluations_run = []

    # Run selected evaluations
    try:
        if run_models:
            print_section("EMBEDDING MODEL COMPARISON")
            run_model_comparison(document_path=args.document, output_dir=args.output)
            evaluations_run.append("Model Comparison")

        if run_hybrid:
            print_section("HYBRID VS SEMANTIC RETRIEVAL")
            run_hybrid_comparison(
                document_path=args.document,
                embedding_model=args.embedding_model,
                output_dir=args.output,
            )
            evaluations_run.append("Hybrid Comparison")

        if run_personas:
            print_section("PERSONA-BASED EVALUATION")
            run_persona_evaluation(
                document_path=args.document,
                embedding_model=args.embedding_model,
                output_dir=args.output,
            )
            evaluations_run.append("Persona Evaluation")

        if run_latency:
            print_section("LATENCY MEASUREMENT")
            run_latency_measurement(
                document_path=args.document,
                embedding_model=args.embedding_model,
                num_runs=args.runs,
                output_dir=args.output,
            )
            evaluations_run.append("Latency Measurement")

        if run_classify:
            print_section("QUERY CLASSIFICATION ACCURACY")
            run_classification_accuracy(output_dir=args.output)
            evaluations_run.append("Classification Accuracy")

        if run_readability:
            print_section("READABILITY ANALYSIS")
            run_readability_analysis(
                document_path=args.document,
                embedding_model=args.embedding_model,
                output_dir=args.output,
            )
            evaluations_run.append("Readability Analysis")

        if run_compliance:
            print_section("FORMAT COMPLIANCE EVALUATION")
            run_format_compliance(
                document_path=args.document,
                embedding_model=args.embedding_model,
                output_dir=args.output,
            )
            evaluations_run.append("Format Compliance")

        if run_adaptive:
            print_section("ADAPTIVE vs GENERIC RAG COMPARISON")
            run_adaptive_vs_generic(
                document_path=args.document,
                embedding_model=args.embedding_model,
                output_dir=args.output,
            )
            evaluations_run.append("Adaptive vs Generic")

        # Always calculate final metrics if we ran any evaluations
        if evaluations_run:
            print_section("CALCULATING FINAL METRICS")
            calculate_all_metrics(results_dir=args.output)

        # Print summary
        print("\n" + "=" * 70)
        print("                     ✅ EVALUATION COMPLETE")
        print("=" * 70)
        print("\nEvaluations completed:")
        for eval_name in evaluations_run:
            print(f"  ✓ {eval_name}")
        print(f"\nResults saved to: {os.path.abspath(args.output)}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️ Evaluation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during evaluation: {e}")
        raise


if __name__ == "__main__":
    main()
