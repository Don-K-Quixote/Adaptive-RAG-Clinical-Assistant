"""
Evaluation Package for Adaptive RAG Clinical Assistant
=======================================================

This package contains evaluation scripts for benchmarking the RAG system.

Modules:
- model_comparison: Compare embedding models on retrieval quality
- persona_evaluation: Evaluate response quality across user personas
- hybrid_comparison: Compare hybrid (RRF) vs semantic-only retrieval
- latency_measurement: Measure end-to-end latency
- classification_accuracy: Query classifier accuracy (no document/LLM needed)
- readability_analysis: Readability metrics per persona
- format_compliance: Format instruction compliance per (persona, query_type)
- adaptive_vs_generic: Head-to-head adaptive RAG vs plain RAG
- metrics: Calculate evaluation metrics

Usage:
    python run_eval.py --help
"""

from .adaptive_vs_generic import run_adaptive_vs_generic
from .classification_accuracy import run_classification_accuracy
from .format_compliance import run_format_compliance
from .hybrid_comparison import run_hybrid_comparison
from .latency_measurement import run_latency_measurement
from .metrics import calculate_all_metrics
from .model_comparison import run_model_comparison
from .persona_evaluation import run_persona_evaluation
from .readability_analysis import run_readability_analysis

__all__ = [
    "run_model_comparison",
    "run_persona_evaluation",
    "run_hybrid_comparison",
    "run_latency_measurement",
    "run_classification_accuracy",
    "run_readability_analysis",
    "run_format_compliance",
    "run_adaptive_vs_generic",
    "calculate_all_metrics",
]
