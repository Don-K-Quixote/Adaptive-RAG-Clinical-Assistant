"""
Generate all 6 benchmark evaluation figures as PNGs using matplotlib.

v2 — layout fixes:
  - Fig 1: wider canvas, benchmark boxes fit without clipping
  - Fig 2: correct arrow targets, whitespace removed, formula inset connected
  - Fig 3: whitespace trimmed, inset repositioned
  - Fig 4: top label no longer cropped, layout spacing corrected
  - Fig 5: per-query phase redrawn as a clear vertical sequence
  - Fig 6: vertical spacing tightened
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUTPUT_DIR = Path("docs/rag-system")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Colours ──────────────────────────────────────────────────────────────────
NAVY       = "#112240"
TEAL       = "#0EA5C9"
TEAL_LIGHT = "#BAE6FD"
SLATE      = "#475569"
WHITE      = "#FFFFFF"
LIGHT_BG   = "#F0F9FF"
ORANGE     = "#EA580C"
GREEN      = "#16A34A"
PURPLE     = "#7C3AED"
GREY       = "#94A3B8"
RED_LIGHT  = "#FEF2F2"
RED_BORDER = "#DC2626"


# ── Primitives ───────────────────────────────────────────────────────────────

def _box(ax, x, y, w, h, label, color=NAVY, text_color=WHITE,
         fontsize=8.5, subtext=None, subtext_size=7):
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.08",
        facecolor=color, edgecolor=WHITE, linewidth=0.8, zorder=3
    )
    ax.add_patch(patch)
    if subtext:
        ax.text(x, y + h * 0.18, label,
                ha="center", va="center", fontsize=fontsize,
                color=text_color, fontweight="bold", zorder=4, multialignment="center")
        ax.text(x, y - h * 0.25, subtext,
                ha="center", va="center", fontsize=subtext_size,
                color=text_color, style="italic", zorder=4, multialignment="center")
    else:
        ax.text(x, y, label,
                ha="center", va="center", fontsize=fontsize,
                color=text_color, fontweight="bold", zorder=4, multialignment="center")


def _arrow(ax, x1, y1, x2, y2, color=SLATE, lw=1.2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=10), zorder=2)


def _inset(ax, x, y, text, width=3.8):
    ax.text(x, y, text,
            fontsize=7.2, color=NAVY, va="top", ha="left",
            bbox=dict(facecolor="#E0F2FE", edgecolor=TEAL,
                      linewidth=1, pad=5, boxstyle="round,pad=0.3"))


def _caption(fig, text):
    fig.text(0.5, 0.015, text, ha="center", fontsize=9.5,
             color=NAVY, fontweight="bold")


def _setup(w=13, h=8, ylim=(0, 10)):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(LIGHT_BG)
    ax.set_facecolor(LIGHT_BG)
    ax.set_xlim(0, 14)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


# ── Figure 1 — Benchmarking Pipeline Flow ────────────────────────────────────

def fig1_pipeline():
    fig, ax = _setup(w=14, h=9, ylim=(0, 10))

    # Input
    _box(ax, 7, 9.3, 5.0, 0.7, "Test Corpus / Clinical Trial PDF", color=NAVY)
    _arrow(ax, 7, 8.95, 7, 8.55)

    # Splitter
    _box(ax, 7, 8.2, 5.0, 0.65,
         "DocumentLoader + RecursiveSemanticSplitter",
         subtext="chunk_size=800  ·  overlap=150", color=SLATE)

    # Fan-out to 4 benchmark boxes (well within 0–14 canvas)
    bx = [2.0, 5.5, 9.0, 12.0]
    blabels = [
        ("model_comparison.py\nrun_model_comparison()", TEAL),
        ("hybrid_comparison.py\nrun_hybrid_comparison()", ORANGE),
        ("persona_evaluation.py\nrun_persona_evaluation()", PURPLE),
        ("latency_measurement.py\nrun_latency_measurement()", GREEN),
    ]
    for x, (lbl, col) in zip(bx, blabels):
        _arrow(ax, 7, 7.87, x, 7.15)
        _box(ax, x, 6.8, 2.6, 0.65, lbl, color=col, fontsize=7.5)

    # Converge to metrics
    _box(ax, 7, 5.7, 4.8, 0.65,
         "eval/metrics.py  ·  calculate_all_metrics()", color=SLATE)
    for x in bx:
        _arrow(ax, x, 6.47, 7, 6.02)

    # Results
    _box(ax, 7, 4.7, 4.0, 0.65, "results/  ·  CSV  ·  JSON  ·  TXT", color=NAVY)
    _arrow(ax, 7, 5.37, 7, 5.03)

    # Streamlit
    _box(ax, 7, 3.7, 4.0, 0.65,
         "Streamlit Evaluate Tab\napp.py : 1115–1535", color=TEAL)
    _arrow(ax, 7, 4.37, 7, 4.03)

    # Summary
    _box(ax, 7, 2.7, 4.0, 0.6, "final_metrics_summary.txt", color=NAVY)
    _arrow(ax, 7, 3.37, 7, 3.0)

    _caption(fig, "Figure 1 — Benchmarking Pipeline Flow")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "fig1_pipeline.png")


# ── Figure 2 — Model Comparison Flow ─────────────────────────────────────────

def fig2_model_comparison():
    # ylim bottom raised to 2.0 to cut dead whitespace
    fig, ax = _setup(w=14, h=7, ylim=(2.0, 9.5))

    # Input
    _box(ax, 2.0, 8.8, 3.0, 0.85,
         "10-Query Test Set\nmedical_technical (7)\nprocedural (1)  ·  general (2)",
         color=NAVY, fontsize=8)

    # 6 model boxes — evenly spaced vertically
    models = [
        ("all-mpnet-base-v2\nGeneral  768-dim", SLATE),
        ("all-MiniLM-L6-v2\nGeneral  384-dim", SLATE),
        ("S-PubMedBert-MS-MARCO\nMedical  768-dim  ★ DEFAULT", TEAL),
        ("BioSimCSE-BioLinkBERT\nMedical  768-dim", GREEN),
        ("BioBERT\nMedical  768-dim", ORANGE),
        ("bert-tiny-mnli\nLightweight  128-dim", PURPLE),
    ]
    my = [8.9, 8.0, 7.1, 6.2, 5.3, 4.4]
    for (lbl, col), y in zip(models, my):
        _arrow(ax, 3.5, 8.8, 4.8, y)
        _box(ax, 6.2, y, 2.7, 0.65, lbl, color=col, fontsize=7.5)

    # Scores box — vertically centred on model list, placed BELOW csv
    score_y = (my[0] + my[-1]) / 2   # ≈ 6.65
    _box(ax, 9.4, score_y, 2.7, 0.85,
         "Per-Model Scores\nindex_time (s)\nretrieval_time_ms  ·  diversity_score",
         color=NAVY, fontsize=8)
    for y in my:
        _arrow(ax, 7.55, y, 8.05, score_y)

    # Output CSV — below the scores box so arrow is clearly vertical
    csv_y = score_y - 1.6
    _box(ax, 9.4, csv_y, 3.2, 0.75,
         "model_comparison_results.csv\nmodel_comparison_summary.txt",
         color=TEAL, fontsize=8)
    _arrow(ax, 9.4, score_y - 0.43, 9.4, csv_y + 0.38)

    # Diversity formula inset — anchored to bottom of canvas
    _inset(ax, 0.3, 3.6,
           "Diversity Score  (src/utils.py: calculate_diversity_score())\n"
           "  diversity = 0.4 × page_div  +  0.6 × content_div\n"
           "  content_div  = 1 – mean pairwise Jaccard similarity\n"
           "  Range: 0.0 (all identical)  →  1.0 (all unique)")

    _caption(fig, "Figure 2 — Model Comparison Flow")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "fig2_model_comparison.png")


# ── Figure 3 — Hybrid vs Semantic Comparison Flow ────────────────────────────

def fig3_hybrid_semantic():
    # ylim tightened: content spans ~3.5 to 8.0
    fig, ax = _setup(w=14, h=7, ylim=(2.5, 9.0))

    # Query
    _box(ax, 1.8, 6.8, 2.8, 0.75,
         "10 Test Queries\nmedical (5)  +  procedural (5)", color=NAVY, fontsize=8.5)

    # Three retrieval paths (vertically shifted up)
    paths = [
        (6.2, 8.2, "Hybrid Retriever\nDense FAISS + BM25 + RRF (k=60)\nsrc/retrieval.py", TEAL),
        (6.2, 6.8, "Semantic Retrieval\nFAISS Dense Only\nHybridRetriever.semantic_only()", ORANGE),
        (6.2, 5.4, "Lexical Retrieval\nBM25 Only\nHybridRetriever.lexical_only()", PURPLE),
    ]
    for cx, cy, lbl, col in paths:
        _arrow(ax, 3.15, 6.8, cx - 1.35, cy)
        _box(ax, cx, cy, 2.65, 0.8, lbl, color=col, fontsize=7.5)

    # Aggregator — centred vertically on paths, separated from output vertically
    agg_y = 6.8
    _box(ax, 9.5, agg_y, 2.8, 0.8,
         "compare_retrieval_methods()\neval/hybrid_comparison.py", color=SLATE, fontsize=8)
    for _, cy, _, _ in paths:
        _arrow(ax, 7.53, cy, 8.1, agg_y)

    # Output — placed BELOW aggregator with clear vertical arrow
    out_y = agg_y - 1.6
    _box(ax, 9.5, out_y, 3.2, 0.8,
         "hybrid_vs_semantic_comparison.csv\nhybrid_vs_semantic_summary.txt",
         color=NAVY, fontsize=7.8)
    _arrow(ax, 9.5, agg_y - 0.4, 9.5, out_y + 0.4)

    # Metrics & formula inset
    _inset(ax, 0.3, 4.7,
           "Metrics per query (eval/hybrid_comparison.py):\n"
           "  • hybrid / semantic / lexical_time_ms\n"
           "  • hybrid / semantic / lexical_diversity\n"
           "  • diversity_improvement  = hybrid_div − semantic_div\n"
           "  • time_overhead_ms       = hybrid_ms − semantic_ms\n\n"
           "RRF formula  (src/config.py: RRF_K_CONSTANT = 60):\n"
           "  score(d) = Σᵢ  1 / (60 + rankᵢ(d))")

    _caption(fig, "Figure 3 — Hybrid vs Semantic Retrieval Comparison Flow")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "fig3_hybrid_semantic.png")


# ── Figure 4 — Persona Evaluation Flow ───────────────────────────────────────

def fig4_persona():
    fig, ax = _setup(w=14, h=10, ylim=(0, 11))

    # Input — lowered so label is never clipped
    _box(ax, 7, 10.3, 3.8, 0.7, "5 Test Queries  (Clinical Trial Topics)", color=NAVY)

    # Two parallel steps from query
    _arrow(ax, 5.1, 10.3, 3.0, 9.45)
    _arrow(ax, 8.9, 10.3, 11.0, 9.45)

    _box(ax, 2.5, 9.1, 3.2, 0.65,
         "QueryClassifier.classify()\nsrc/query_classifier.py", color=SLATE, fontsize=7.8)
    _box(ax, 11.5, 9.1, 3.2, 0.65,
         "HybridRetriever.retrieve()\ntop_k = 5", color=TEAL, fontsize=7.8)

    # Prompt builder
    _box(ax, 7, 8.0, 3.8, 0.65,
         "build_adaptive_prompt()\nsrc/prompts.py", color=SLATE)
    _arrow(ax, 2.5, 8.77, 5.1, 8.33)
    _arrow(ax, 11.5, 8.77, 8.9, 8.33)

    # ResponseConfig
    _box(ax, 7, 7.0, 3.8, 0.6,
         "get_response_config(UserType, QueryType)\nsrc/personas.py", color=ORANGE, fontsize=7.8)
    _arrow(ax, 7, 7.67, 7, 7.3)

    # Five persona boxes
    personas = [
        (1.4,  5.5, "NOVICE\nmax 300 words\ninclude_definitions\nuse_bullet_points", GREEN),
        (4.2,  5.5, "INTERMEDIATE\nmax 500 words\nuse_tables\ninclude_examples", TEAL),
        (7.0,  5.5, "EXPERT\nmax 1000 words\nuse_tables\ninclude_references", NAVY),
        (9.8,  5.5, "REGULATORY\nmax 800 words\ncolor_coding\ninclude_references", ORANGE),
        (12.6, 5.5, "EXECUTIVE\nmax 250 words\nexec_summary\nrecommendations", PURPLE),
    ]
    for cx, cy, lbl, col in personas:
        _arrow(ax, 7, 6.7, cx, cy + 0.62)
        _box(ax, cx, cy, 2.3, 1.2, lbl, color=col, fontsize=7.2)

    # Collector
    _box(ax, 7, 4.0, 3.8, 0.65,
         "evaluate_persona_responses()\neval/persona_evaluation.py", color=SLATE)
    for cx, cy, _, _ in personas:
        _arrow(ax, cx, cy - 0.62, 7, 4.33)

    # Outputs
    _box(ax, 4.0, 2.8, 3.5, 0.65,
         "persona_responses.json\n(25 response objects)", color=NAVY, fontsize=8)
    _box(ax, 10.0, 2.8, 3.5, 0.65,
         "persona_responses_formatted.html\n(human-readable report)", color=NAVY, fontsize=7.8)
    _arrow(ax, 7, 3.67, 4.0, 3.13)
    _arrow(ax, 7, 3.67, 10.0, 3.13)

    _caption(fig, "Figure 4 — Persona Evaluation Flow")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "fig4_persona.png")


# ── Figure 5 — Latency Measurement Flow ──────────────────────────────────────

def fig5_latency():
    """Two-column layout: setup chain (left) | per-query vertical pipeline (right)."""
    fig, ax = _setup(w=14, h=9, ylim=(0, 10))

    # ── Column headers ──
    ax.text(3.0, 9.6, "SETUP PHASE  (one-time)",
            fontsize=9.5, fontweight="bold", color=NAVY, ha="center",
            bbox=dict(facecolor=TEAL_LIGHT, edgecolor=TEAL, linewidth=1,
                      pad=5, boxstyle="round,pad=0.3"))
    ax.text(10.5, 9.6, "PER-QUERY PHASE  (× num_runs = 3, then averaged)",
            fontsize=9.5, fontweight="bold", color=NAVY, ha="center",
            bbox=dict(facecolor=TEAL_LIGHT, edgecolor=TEAL, linewidth=1,
                      pad=5, boxstyle="round,pad=0.3"))

    # ── Setup chain (vertical, left column) ──
    setup = [
        ("Document Loading\ndoc_loading_time (s)",             SLATE),
        ("Chunking\nchunking_time (s)\nchunk_size=800, overlap=150", SLATE),
        ("Embedder Loading\nembedder_loading_time (s)",         SLATE),
        ("FAISS Vector Indexing\nvector_indexing_time (s)",      SLATE),
        ("BM25 Indexing\nbm25_indexing_time (s)",               SLATE),
    ]
    sy = [8.8, 7.7, 6.6, 5.5, 4.4]
    for (lbl, col), y in zip(setup, sy):
        _box(ax, 3.0, y, 4.5, 0.75, lbl, color=col, fontsize=8)
    for y1, y2 in zip(sy[:-1], sy[1:]):
        _arrow(ax, 3.0, y1 - 0.38, 3.0, y2 + 0.38)

    # ── Per-query pipeline (vertical, right column) ──
    stages = [
        (10.5, 8.8, "Query In\n5 test queries",                          NAVY),
        (10.5, 7.5, "HybridRetriever.retrieve()\nt₀ → t₁  =  retrieval_ms",  TEAL),
        (10.5, 6.2, "build_adaptive_prompt()\nUserType.INTERMEDIATE",     SLATE),
        (10.5, 4.9, "LLM Generation  (gpt-4o-mini)\nt₂ → t₃  =  generation_ms", ORANGE),
        (10.5, 3.6, "measure_pipeline_latency()\nmean / std / min / max over 3 runs", GREEN),
        (10.5, 2.3, "latency_results.csv\nlatency_summary.txt",           NAVY),
    ]
    for cx, cy, lbl, col in stages:
        _box(ax, cx, cy, 4.5, 0.75, lbl, color=col, fontsize=8)
    for (_, y1, _, _), (_, y2, _, _) in zip(stages[:-1], stages[1:]):
        _arrow(ax, 10.5, y1 - 0.38, 10.5, y2 + 0.38)

    # Divider
    ax.axvline(x=5.5, ymin=0.08, ymax=0.98, color=GREY,
               linestyle="--", linewidth=1.2, zorder=1)

    # Aggregation inset (below pipeline, raised to avoid canvas clipping)
    _inset(ax, 6.5, 2.5,
           "eval/metrics.py: calculate_latency_metrics()\n"
           "  → avg_retrieval_ms,  avg_generation_ms,  avg_total_ms\n"
           "  → p50_total_ms,  p95_total_ms,  max_total_ms")

    _caption(fig, "Figure 5 — Latency Measurement Flow")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "fig5_latency.png")


# ── Figure 6 — Results Storage & Aggregation Flow ────────────────────────────

def fig6_results_storage():
    fig, ax = _setup(w=14, h=9, ylim=(0, 10))

    bench_files = [
        "model_comparison_results.csv",
        "hybrid_vs_semantic_comparison.csv",
        "latency_results.csv",
        "persona_responses.json",
    ]
    adapt_files = [
        "classification_accuracy_results.csv",
        "readability_analysis_results.csv",
        "format_compliance_results.csv",
        "adaptive_vs_generic_results.csv",
    ]

    # Column labels
    ax.text(2.8, 9.5, "Benchmark Evals (4)", fontsize=9, color=TEAL,
            ha="center", fontweight="bold")
    ax.text(11.2, 9.5, "Adaptive Evals (4)", fontsize=9, color=ORANGE,
            ha="center", fontweight="bold")

    # Left column — benchmark files
    for i, f in enumerate(bench_files):
        y = 8.8 - i * 1.0
        _box(ax, 2.8, y, 4.5, 0.65, f, color=TEAL, fontsize=8)
        _arrow(ax, 5.05, y, 6.5, 5.8)

    # Right column — adaptive files
    for i, f in enumerate(adapt_files):
        y = 8.8 - i * 1.0
        _box(ax, 11.2, y, 4.5, 0.65, f, color=ORANGE, fontsize=8)
        _arrow(ax, 8.95, y, 7.5, 5.8)

    # Central aggregator
    _box(ax, 7.0, 5.4, 4.2, 0.75,
         "eval/metrics.py\ncalculate_all_metrics(results_dir)", color=SLATE, fontsize=8.5)

    # Summary
    _box(ax, 7.0, 4.1, 4.0, 0.65, "final_metrics_summary.txt  ·  results/", color=NAVY)
    _arrow(ax, 7.0, 5.02, 7.0, 4.43)

    # Streamlit
    _box(ax, 7.0, 2.9, 4.2, 0.75,
         "Streamlit Evaluate Tab\napp.py : 1115–1535\nst.session_state.benchmark_results",
         color=TEAL, fontsize=7.8)
    _arrow(ax, 7.0, 3.77, 7.0, 3.27)

    # Outputs
    _box(ax, 4.0, 1.6, 3.5, 0.65, "CSV / TXT\nDownload Buttons", color=SLATE, fontsize=8)
    _box(ax, 10.0, 1.6, 3.5, 0.65, "Metrics Cards\n(inline display)", color=SLATE, fontsize=8)
    _arrow(ax, 7.0, 2.52, 4.0, 1.93)
    _arrow(ax, 7.0, 2.52, 10.0, 1.93)

    # Warning
    ax.text(0.5, 0.9,
            "⚠  No run versioning: each benchmark run overwrites the previous results/ files.",
            fontsize=8, color=RED_BORDER, va="top",
            bbox=dict(facecolor=RED_LIGHT, edgecolor=RED_BORDER,
                      linewidth=1.2, pad=5, boxstyle="round,pad=0.3"))

    _caption(fig, "Figure 6 — Results Storage & Aggregation Flow")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _save(fig, "fig6_results_storage.png")


# ── Save helper ───────────────────────────────────────────────────────────────

def _save(fig, name):
    out = OUTPUT_DIR / name
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=LIGHT_BG)
    plt.close(fig)
    print(f"Saved {out}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    fig1_pipeline()
    fig2_model_comparison()
    fig3_hybrid_semantic()
    fig4_persona()
    fig5_latency()
    fig6_results_storage()
    print("\nAll 6 figures generated.")
