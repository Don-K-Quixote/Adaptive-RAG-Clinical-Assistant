"""
Model Comparison Evaluation
===========================

Compares embedding models on retrieval quality metrics including:
- Retrieval time
- Result diversity
- Query type performance

Output:
- results/model_comparison_results.csv
- results/model_comparison_summary.txt
"""

import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, EMBEDDING_MODELS, HNSW_COLLECTION_METADATA
from src.embeddings import create_embedder
from src.utils import calculate_diversity_score

# Default test queries
DEFAULT_QUERIES = [
    {"query": "How to measure target lesions under RECIST 1.1?", "type": "medical_technical"},
    {"query": "What is the definition of partial response?", "type": "medical_technical"},
    {"query": "Baseline imaging schedule requirements", "type": "procedural"},
    {"query": "How to calculate SUVmax?", "type": "medical_technical"},
    {"query": "Lymph node measurement criteria", "type": "medical_technical"},
    {"query": "What are non-target lesions?", "type": "medical_technical"},
    {"query": "Progressive disease assessment", "type": "general"},
    {"query": "When is a scan considered evaluable?", "type": "general"},
    {"query": "PET/CT scan timing requirements", "type": "medical_technical"},
    {"query": "Adverse event reporting for contrast reactions", "type": "medical_technical"},
]


def load_and_chunk_document(
    file_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
) -> list:
    """Load and chunk a PDF document."""
    print(f"📄 Loading document: {file_path}")

    loader = PyPDFLoader(file_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""],
    )

    chunks = splitter.split_documents(pages)

    # Add metadata
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i

    print(f"✅ Loaded {len(pages)} pages, {len(chunks)} chunks")
    return chunks


def evaluate_model(
    model_key: str, chunks: list, queries: list[dict], output_dir: str = "results"
) -> dict:
    """Evaluate a single embedding model."""
    print(f"\n🔧 Evaluating: {model_key}")

    # Create embedder
    embedder = create_embedder(model_key)
    if not embedder:
        print(f"❌ Failed to load {model_key}")
        return None

    # Build vector store
    persist_dir = os.path.join(output_dir, f"chroma_{model_key.replace('/', '_')}")

    start_index = time.time()
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=persist_dir,
        collection_metadata=HNSW_COLLECTION_METADATA,
    )
    index_time = time.time() - start_index
    print(f"   Index time: {index_time:.2f}s")

    # Evaluate queries
    results = []
    retriever = vectordb.as_retriever(search_kwargs={"k": 5})

    for q_data in queries:
        query = q_data["query"]
        query_type = q_data["type"]

        start = time.time()
        docs = retriever.invoke(query)
        retrieval_time = (time.time() - start) * 1000  # ms

        diversity = calculate_diversity_score(docs)

        results.append(
            {
                "model": model_key,
                "model_type": EMBEDDING_MODELS[model_key]["type"],
                "query": query,
                "query_type": query_type,
                "retrieval_time_ms": retrieval_time,
                "diversity_score": diversity,
                "num_results": len(docs),
            }
        )

    return {
        "model": model_key,
        "index_time": index_time,
        "results": results,
    }


def run_model_comparison(
    document_path: str,
    models: list[str] | None = None,
    queries: list[dict] | None = None,
    output_dir: str = "results",
) -> pd.DataFrame:
    """
    Run comparison across multiple embedding models.

    Args:
        document_path: Path to PDF document
        models: List of model keys to compare (default: all models)
        queries: List of query dicts with 'query' and 'type' keys
        output_dir: Directory for output files

    Returns:
        DataFrame with comparison results
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load document
    chunks = load_and_chunk_document(document_path)

    # Default to all models if not specified
    if models is None:
        models = list(EMBEDDING_MODELS.keys())

    # Default queries
    if queries is None:
        queries = DEFAULT_QUERIES

    # Evaluate each model
    all_results = []
    model_summaries = []

    for model_key in models:
        if model_key not in EMBEDDING_MODELS:
            print(f"⚠️ Unknown model: {model_key}, skipping")
            continue

        eval_result = evaluate_model(model_key, chunks, queries, output_dir)

        if eval_result:
            all_results.extend(eval_result["results"])
            model_summaries.append(
                {
                    "model": model_key,
                    "type": EMBEDDING_MODELS[model_key]["type"],
                    "dimensions": EMBEDDING_MODELS[model_key]["dimensions"],
                    "index_time_s": eval_result["index_time"],
                    "avg_retrieval_ms": np.mean(
                        [r["retrieval_time_ms"] for r in eval_result["results"]]
                    ),
                    "avg_diversity": np.mean(
                        [r["diversity_score"] for r in eval_result["results"]]
                    ),
                }
            )

    # Create DataFrames
    results_df = pd.DataFrame(all_results)
    summary_df = pd.DataFrame(model_summaries)

    # Save results
    results_path = os.path.join(output_dir, "model_comparison_results.csv")
    results_df.to_csv(results_path, index=False)
    print(f"\n💾 Saved: {results_path}")

    # Save summary
    summary_path = os.path.join(output_dir, "model_comparison_summary.txt")
    with open(summary_path, "w") as f:
        f.write("MODEL COMPARISON SUMMARY\n")
        f.write("=" * 60 + "\n\n")

        for _, row in summary_df.iterrows():
            f.write(f"{row['model']}\n")
            f.write("-" * 60 + "\n")
            f.write(f"Type: {row['type']}\n")
            f.write(f"Dimensions: {row['dimensions']}\n")
            f.write(f"Index Time: {row['index_time_s']:.2f}s\n")
            f.write(f"Avg Retrieval Time: {row['avg_retrieval_ms']:.2f}ms\n")
            f.write(f"Avg Diversity Score: {row['avg_diversity']:.3f}\n\n")

        f.write("\n" + "=" * 60 + "\n")
        f.write("BEST PERFORMERS\n")
        f.write("-" * 60 + "\n")

        fastest = summary_df.loc[summary_df["avg_retrieval_ms"].idxmin(), "model"]
        highest_div = summary_df.loc[summary_df["avg_diversity"].idxmax(), "model"]

        f.write(f"Fastest Retrieval: {fastest}\n")
        f.write(f"Highest Diversity: {highest_div}\n")

    print(f"💾 Saved: {summary_path}")

    return results_df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare embedding models")
    parser.add_argument("--document", type=str, required=True, help="Path to PDF document")
    parser.add_argument("--output", type=str, default="results", help="Output directory")

    args = parser.parse_args()

    run_model_comparison(document_path=args.document, output_dir=args.output)
