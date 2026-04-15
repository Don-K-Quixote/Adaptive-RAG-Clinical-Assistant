"""
Adaptive vs Generic RAG Head-to-Head Comparison
================================================

Proves that the full adaptive pipeline beats a vanilla RAG baseline on a
composite quality score.

Both systems use the same PDF, embedding model, and LLM. The difference is:
- Generic:  semantic-only retrieval + static prompt
- Adaptive: HybridRetriever (RRF) + persona-aware / query-type-aware prompt

Output:
- results/adaptive_vs_generic_results.csv
- results/adaptive_vs_generic_detailed.json
- results/adaptive_vs_generic_summary.txt
"""

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import textstat
except ImportError as exc:
    raise ImportError(
        "textstat is required. Install with: conda install -c conda-forge textstat"
    ) from exc

from dotenv import find_dotenv, load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

from src.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_LLM_MODEL,
    HNSW_COLLECTION_METADATA,
)
from src.embeddings import create_embedder
from src.personas import UserType, get_response_config
from src.prompts import build_adaptive_prompt
from src.query_classifier import classify_query
from src.retrieval import HybridRetriever

from .format_compliance import compute_compliance_score

load_dotenv(find_dotenv())

# ---------------------------------------------------------------------------
# Persona-to-expected Flesch-Kincaid grade targets
# ---------------------------------------------------------------------------

PERSONA_GRADE_TARGETS: dict[str, tuple[float, float]] = {
    "novice": (6.0, 9.0),
    "intermediate": (10.0, 13.0),
    "expert": (14.0, 18.0),
    "regulatory": (14.0, 18.0),
    "executive": (8.0, 12.0),
}

# ---------------------------------------------------------------------------
# Default comparison query set — 25 queries, 5 per persona, covering all
# 9 query types
# ---------------------------------------------------------------------------

COMPARISON_QUERIES: list[dict] = [
    # ----- novice (5) -----
    {"query": "What is RECIST 1.1?", "type": "definition", "persona": "novice"},
    {
        "query": "How many target lesions can be measured per organ?",
        "type": "numerical",
        "persona": "novice",
    },
    {
        "query": "What are the inclusion criteria for patients in this study?",
        "type": "eligibility",
        "persona": "novice",
    },
    {"query": "What safety issues should I watch out for?", "type": "safety", "persona": "novice"},
    {
        "query": "How do I measure a patient's response to treatment?",
        "type": "procedure",
        "persona": "novice",
    },
    # ----- intermediate (5) -----
    {
        "query": "Compare CT and MRI for tumor assessment",
        "type": "comparison",
        "persona": "intermediate",
    },
    {
        "query": "What is the imaging schedule for this study?",
        "type": "timeline",
        "persona": "intermediate",
    },
    {
        "query": "What are the compliance requirements for imaging documentation?",
        "type": "compliance",
        "persona": "intermediate",
    },
    {
        "query": "How are adverse events graded in this protocol?",
        "type": "safety",
        "persona": "intermediate",
    },
    {
        "query": "What defines partial versus complete response?",
        "type": "definition",
        "persona": "intermediate",
    },
    # ----- expert (5) -----
    {
        "query": "How does RECIST 1.1 differ from iRECIST for immunotherapy trials?",
        "type": "comparison",
        "persona": "expert",
    },
    {
        "query": "What are the statistical criteria and procedures for stopping the trial?",
        "type": "complex",
        "persona": "expert",
    },
    {
        "query": "How many target lesions are allowed per organ per RECIST 1.1?",
        "type": "numerical",
        "persona": "expert",
    },
    {
        "query": "What GCP guidelines govern SAE reporting timelines under ICH?",
        "type": "compliance",
        "persona": "expert",
    },
    {
        "query": "Describe the inclusion and exclusion criteria for this study",
        "type": "eligibility",
        "persona": "expert",
    },
    # ----- regulatory (5) -----
    {
        "query": "What FDA documentation is required for protocol amendments?",
        "type": "compliance",
        "persona": "regulatory",
    },
    {
        "query": "How should protocol deviations be handled under ICH-GCP?",
        "type": "procedure",
        "persona": "regulatory",
    },
    {
        "query": "What are the regulatory timelines for SAE reporting to the sponsor?",
        "type": "timeline",
        "persona": "regulatory",
    },
    {
        "query": "What are the audit trail and documentation requirements?",
        "type": "compliance",
        "persona": "regulatory",
    },
    {
        "query": "Compare EMA and FDA requirements for informed consent documentation",
        "type": "comparison",
        "persona": "regulatory",
    },
    # ----- executive (5) -----
    {
        "query": "What is the overall efficacy profile of this treatment?",
        "type": "definition",
        "persona": "executive",
    },
    {
        "query": "How does this trial compare to competing studies in the field?",
        "type": "comparison",
        "persona": "executive",
    },
    {
        "query": "What is the projected timeline for trial completion and key milestones?",
        "type": "timeline",
        "persona": "executive",
    },
    {
        "query": "What are the key safety signals we need to monitor?",
        "type": "safety",
        "persona": "executive",
    },
    {
        "query": "How many patients are eligible and what is the enrollment forecast?",
        "type": "numerical",
        "persona": "executive",
    },
]


def build_generic_prompt(context: str, query: str) -> str:
    """
    Build a static, persona-free prompt for the generic RAG baseline.

    This intentionally has no persona instructions, audience tailoring,
    or query-type-specific formatting — the minimum viable RAG prompt.

    Args:
        context: Retrieved document text (joined chunks).
        query: User query string.

    Returns:
        Prompt string suitable for direct LLM invocation.
    """
    return (
        "You are a helpful assistant. Use the following context to answer the question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )


def _join_docs(documents: list) -> str:
    """Join a list of LangChain Document objects into a single context string."""
    return "\n\n".join(doc.page_content for doc in documents)


def run_adaptive_vs_generic(
    document_path: str,
    queries: list[dict] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    llm_model: str = DEFAULT_LLM_MODEL,
    output_dir: str = "results",
) -> pd.DataFrame:
    """
    Run a head-to-head comparison of adaptive RAG vs generic RAG.

    For each query both systems retrieve from the same document using the
    same embedding model and LLM. The only differences are retrieval method
    (HybridRetriever vs semantic-only) and prompt construction.

    Args:
        document_path: Path to the source PDF document.
        queries: List of dicts with keys 'query', 'type', 'persona'.
                 Defaults to COMPARISON_QUERIES.
        embedding_model: Embedding model identifier.
        llm_model: LLM model identifier.
        output_dir: Directory for output files.

    Returns:
        DataFrame with one row per query.
    """
    os.makedirs(output_dir, exist_ok=True)

    query_list = queries if queries is not None else COMPARISON_QUERIES

    print(f"[LOAD] Loading document: {document_path}")

    loader = PyPDFLoader(document_path)
    pages = loader.load()

    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i

    print(f"[LOAD] {len(pages)} pages, {len(chunks)} chunks")

    print(f"[EMBED] Creating embeddings with {embedding_model}...")
    embedder = create_embedder(embedding_model)

    persist_dir = os.path.join(output_dir, f"chroma_avsg_{embedding_model.replace('/', '_')}")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=persist_dir,
        collection_metadata=HNSW_COLLECTION_METADATA,
    )

    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 5

    hybrid_retriever = HybridRetriever(
        vectordb=vectordb,
        bm25_retriever=bm25_retriever,
        top_k=5,
    )

    llm = ChatOpenAI(model=llm_model, temperature=0)

    rows = []
    detailed_results = []

    for i, item in enumerate(query_list, 1):
        query = item["query"]
        query_type_str = item["type"]
        persona_str = item["persona"]

        print(f"\n[{i}/{len(query_list)}] {persona_str.upper()} | {query[:55]}...")

        # --- Adaptive system ---
        adaptive_docs = hybrid_retriever.retrieve(query, top_k=5)
        query_type = classify_query(query)

        try:
            user_type = UserType(persona_str)
        except ValueError:
            user_type = UserType.NOVICE

        response_config = get_response_config(user_type, query_type.value)
        adaptive_prompt = build_adaptive_prompt(adaptive_docs, query, response_config)

        start = time.time()
        adaptive_response = llm.invoke(adaptive_prompt).content
        adaptive_gen_ms = (time.time() - start) * 1000

        # --- Generic baseline ---
        generic_docs = vectordb.similarity_search(query, k=5)
        generic_context = _join_docs(generic_docs)
        generic_prompt = build_generic_prompt(generic_context, query)

        start = time.time()
        generic_response = llm.invoke(generic_prompt).content
        generic_gen_ms = (time.time() - start) * 1000

        # --- Compute metrics ---
        adaptive_compliance = compute_compliance_score(
            adaptive_response, query_type_str, persona_str
        )
        generic_compliance = compute_compliance_score(generic_response, query_type_str, persona_str)
        compliance_delta = adaptive_compliance - generic_compliance

        adaptive_ease = textstat.flesch_reading_ease(adaptive_response)
        generic_ease = textstat.flesch_reading_ease(generic_response)
        adaptive_fk_grade = textstat.flesch_kincaid_grade(adaptive_response)
        generic_fk_grade = textstat.flesch_kincaid_grade(generic_response)

        grade_target = PERSONA_GRADE_TARGETS.get(persona_str, (0.0, 100.0))
        persona_appropriate = grade_target[0] <= adaptive_fk_grade <= grade_target[1]

        adaptive_words = len(adaptive_response.split())
        generic_words = len(generic_response.split())
        adaptive_target = response_config.max_length
        generic_target = 500  # neutral baseline

        adaptive_length_adherence = max(
            0.0, 1.0 - abs(adaptive_words - adaptive_target) / max(adaptive_target, 1)
        )
        generic_length_adherence = max(
            0.0, 1.0 - abs(generic_words - generic_target) / max(generic_target, 1)
        )

        wins_compliance = adaptive_compliance > generic_compliance
        wins_readability = persona_appropriate
        wins_length = adaptive_length_adherence > generic_length_adherence
        overall_win = sum([wins_compliance, wins_readability, wins_length]) >= 2

        # Adaptive Advantage Score: composite mean of three normalised deltas.
        # Each component is mapped to [0, 1] so they are directly comparable.
        #   compliance_delta_norm : (delta + 1) / 2  maps [-1, 1] → [0, 1]
        #   readability_fit_score : 1.0 if FK grade within target range, else 0.0
        #   length_delta_norm     : (delta + 1) / 2  maps [-1, 1] → [0, 1]
        compliance_delta_norm = (compliance_delta + 1.0) / 2.0
        readability_fit_score = 1.0 if persona_appropriate else 0.0
        length_delta = adaptive_length_adherence - generic_length_adherence
        length_delta_norm = (length_delta + 1.0) / 2.0
        adaptive_advantage_score = round(
            (compliance_delta_norm + readability_fit_score + length_delta_norm) / 3.0, 4
        )

        row = {
            "query": query,
            "persona": persona_str,
            "query_type": query_type_str,
            "adaptive_compliance_score": round(adaptive_compliance, 3),
            "generic_compliance_score": round(generic_compliance, 3),
            "compliance_delta": round(compliance_delta, 3),
            "adaptive_flesch_ease": round(adaptive_ease, 2),
            "generic_flesch_ease": round(generic_ease, 2),
            "adaptive_fk_grade": round(adaptive_fk_grade, 2),
            "generic_fk_grade": round(generic_fk_grade, 2),
            "persona_appropriate_readability": persona_appropriate,
            "adaptive_word_count": adaptive_words,
            "generic_word_count": generic_words,
            "adaptive_max_length_target": adaptive_target,
            "adaptive_length_adherence": round(adaptive_length_adherence, 3),
            "generic_length_adherence": round(generic_length_adherence, 3),
            "adaptive_wins_compliance": wins_compliance,
            "adaptive_wins_readability_fit": wins_readability,
            "adaptive_wins_length_adherence": wins_length,
            "adaptive_overall_wins": overall_win,
            "adaptive_advantage_score": adaptive_advantage_score,
        }
        rows.append(row)

        detailed_results.append(
            {
                **row,
                "adaptive_response": adaptive_response,
                "generic_response": generic_response,
                "adaptive_gen_ms": round(adaptive_gen_ms, 1),
                "generic_gen_ms": round(generic_gen_ms, 1),
            }
        )

        print(
            f"   adaptive compliance={adaptive_compliance:.2f} "
            f"generic compliance={generic_compliance:.2f} "
            f"win={overall_win}"
        )

    df = pd.DataFrame(rows)

    # Save CSV
    csv_path = os.path.join(output_dir, "adaptive_vs_generic_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SAVED] {csv_path}")

    # Save detailed JSON
    json_path = os.path.join(output_dir, "adaptive_vs_generic_detailed.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(detailed_results, f, indent=2, ensure_ascii=False)
    print(f"[SAVED] {json_path}")

    # Save summary
    summary_path = os.path.join(output_dir, "adaptive_vs_generic_summary.txt")
    _write_summary(df, summary_path)
    print(f"[SAVED] {summary_path}")

    win_rate = df["adaptive_overall_wins"].mean()
    avg_adv = df["adaptive_advantage_score"].mean()
    print(f"\n[RESULT] Adaptive win rate:       {win_rate:.1%}")
    print(f"[RESULT] Adaptive advantage score: {avg_adv:.4f}")

    return df


def _write_summary(df: pd.DataFrame, output_path: str) -> None:
    """Write a human-readable head-to-head comparison summary."""
    win_rate = df["adaptive_overall_wins"].mean()
    compliance_delta = df["compliance_delta"].mean()
    readability_fit_pct = df["persona_appropriate_readability"].mean()
    avg_advantage_score = df["adaptive_advantage_score"].mean()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("        ADAPTIVE vs GENERIC RAG — HEAD-TO-HEAD COMPARISON\n")
        f.write("=" * 70 + "\n\n")

        f.write(
            f"Adaptive Win Rate:          {win_rate:.1%} ({df['adaptive_overall_wins'].sum()}/{len(df)} queries)\n"
        )
        f.write(f"Avg Compliance Delta:        {compliance_delta:+.3f}\n")
        f.write(f"Readability Fit (adaptive):  {readability_fit_pct:.1%}\n")
        f.write(
            f"Adaptive Advantage Score:    {avg_advantage_score:.4f}  "
            f"(mean of normalised compliance, readability, length deltas)\n\n"
        )

        # Per-persona win rate
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  WIN RATE BY PERSONA" + " " * 47 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(
            f"{'Persona':<15} {'Win Rate':<12} {'Compliance Δ':<15} "
            f"{'Readability Fit':<16} {'Adv Score':<10}\n"
        )
        f.write("-" * 72 + "\n")

        persona_order = ["novice", "intermediate", "expert", "regulatory", "executive"]
        for persona in persona_order:
            pdata = df[df["persona"] == persona]
            if pdata.empty:
                continue
            p_win = pdata["adaptive_overall_wins"].mean()
            p_delta = pdata["compliance_delta"].mean()
            p_read = pdata["persona_appropriate_readability"].mean()
            p_adv = pdata["adaptive_advantage_score"].mean()
            f.write(
                f"{persona.title():<15} {p_win:<12.1%} {p_delta:<15.3f} "
                f"{p_read:<16.1%} {p_adv:<10.4f}\n"
            )

        f.write("\n")

        # Per-query-type win rate
        f.write("+" + "-" * 68 + "+\n")
        f.write("|  WIN RATE BY QUERY TYPE" + " " * 44 + "|\n")
        f.write("+" + "-" * 68 + "+\n\n")
        f.write(f"{'Query Type':<20} {'Win Rate':<12} {'N':<6}\n")
        f.write("-" * 40 + "\n")

        for qtype in sorted(df["query_type"].unique()):
            qdata = df[df["query_type"] == qtype]
            q_win = qdata["adaptive_overall_wins"].mean()
            f.write(f"{qtype.title():<20} {q_win:<12.1%} {len(qdata):<6}\n")

        f.write("\n")
        f.write("=" * 70 + "\n")
        f.write("                          END OF REPORT\n")
        f.write("=" * 70 + "\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run adaptive vs generic comparison")
    parser.add_argument("--document", type=str, required=True)
    parser.add_argument("--output", type=str, default="results")
    parser.add_argument("--model", type=str, default="S-PubMedBert-MS-MARCO")
    args = parser.parse_args()

    run_adaptive_vs_generic(
        document_path=args.document,
        embedding_model=args.model,
        output_dir=args.output,
    )
