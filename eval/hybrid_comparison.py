"""
Hybrid vs Semantic Retrieval Comparison
=======================================

Compares hybrid retrieval (RRF) against semantic-only retrieval.

Metrics:
- Retrieval time
- Result diversity
- Overlap analysis (found in both retrievers)

Output:
- results/hybrid_vs_semantic_comparison.csv
- results/hybrid_vs_semantic_summary.txt
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, HNSW_COLLECTION_METADATA
from src.embeddings import create_embedder
from src.retrieval import HybridRetriever
from src.utils import calculate_diversity_score

# Test queries grouped by type
DEFAULT_QUERIES = [
    # Medical/Technical queries
    {"query": "How to measure target lesions under RECIST 1.1?", "type": "medical"},
    {"query": "What is the definition of partial response?", "type": "medical"},
    {"query": "SUVmax calculation methodology", "type": "medical"},
    {"query": "Lymph node measurement criteria", "type": "medical"},
    {"query": "Non-target lesion assessment", "type": "medical"},
    # Procedural queries
    {"query": "Baseline imaging schedule requirements", "type": "procedural"},
    {"query": "When to perform follow-up scans", "type": "procedural"},
    {"query": "How to submit imaging data", "type": "procedural"},
    {"query": "Quality control procedures for CT scans", "type": "procedural"},
    {"query": "Adverse event reporting timeline", "type": "procedural"},
]


def compare_retrieval_methods(
    query: str, hybrid_retriever: HybridRetriever, top_k: int = 5
) -> dict:
    """
    Compare hybrid vs semantic retrieval for a single query.

    Args:
        query: Search query
        hybrid_retriever: Configured HybridRetriever
        top_k: Number of results to retrieve

    Returns:
        Dictionary with comparison metrics
    """
    # Hybrid retrieval (RRF)
    start_hybrid = time.time()
    hybrid_result = hybrid_retriever.retrieve_with_metadata(query, top_k=top_k)
    hybrid_time = (time.time() - start_hybrid) * 1000

    hybrid_docs = hybrid_result["documents"]
    hybrid_diversity = calculate_diversity_score(hybrid_docs)

    # Semantic-only retrieval
    start_semantic = time.time()
    semantic_docs = hybrid_retriever.semantic_only(query, top_k=top_k)
    semantic_time = (time.time() - start_semantic) * 1000

    semantic_diversity = calculate_diversity_score(semantic_docs)

    # Lexical-only retrieval (for reference)
    start_lexical = time.time()
    lexical_docs = hybrid_retriever.lexical_only(query, top_k=top_k)
    lexical_time = (time.time() - start_lexical) * 1000

    lexical_diversity = calculate_diversity_score(lexical_docs)

    # Calculate overlap
    hybrid_ids = set(d.metadata.get("chunk_id", i) for i, d in enumerate(hybrid_docs))
    semantic_ids = set(d.metadata.get("chunk_id", i) for i, d in enumerate(semantic_docs))
    lexical_ids = set(d.metadata.get("chunk_id", i) for i, d in enumerate(lexical_docs))

    hybrid_semantic_overlap = len(hybrid_ids & semantic_ids)
    hybrid_lexical_overlap = len(hybrid_ids & lexical_ids)
    semantic_lexical_overlap = len(semantic_ids & lexical_ids)

    return {
        "query": query,
        # Hybrid metrics
        "hybrid_time_ms": hybrid_time,
        "hybrid_diversity": hybrid_diversity,
        "hybrid_in_both": hybrid_result["stats"].get("found_in_both", 0),
        # Semantic metrics
        "semantic_time_ms": semantic_time,
        "semantic_diversity": semantic_diversity,
        # Lexical metrics
        "lexical_time_ms": lexical_time,
        "lexical_diversity": lexical_diversity,
        # Overlap metrics
        "hybrid_semantic_overlap": hybrid_semantic_overlap,
        "hybrid_lexical_overlap": hybrid_lexical_overlap,
        "semantic_lexical_overlap": semantic_lexical_overlap,
        # Improvement
        "diversity_improvement": hybrid_diversity - semantic_diversity,
        "time_overhead_ms": hybrid_time - semantic_time,
    }


def run_hybrid_comparison(
    document_path: str,
    queries: list[dict] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    output_dir: str = "results",
) -> pd.DataFrame:
    """
    Run hybrid vs semantic comparison across multiple queries.

    Args:
        document_path: Path to PDF document
        queries: List of query dicts with 'query' and 'type' keys
        embedding_model: Embedding model to use
        output_dir: Directory for output files

    Returns:
        DataFrame with comparison results
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"📄 Loading document: {document_path}")

    # Load and chunk document
    loader = PyPDFLoader(document_path)
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i

    print(f"✅ Loaded {len(pages)} pages, {len(chunks)} chunks")

    # Create embedder and vector store
    print(f"🔧 Creating embeddings with {embedding_model}...")
    embedder = create_embedder(embedding_model)

    persist_dir = os.path.join(output_dir, f"chroma_hybrid_{embedding_model.replace('/', '_')}")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=persist_dir,
        collection_metadata=HNSW_COLLECTION_METADATA,
    )

    # Create BM25 retriever
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 10  # More candidates for fusion

    # Create hybrid retriever
    hybrid_retriever = HybridRetriever(vectordb=vectordb, bm25_retriever=bm25_retriever, top_k=5)

    # Use default queries if not provided
    if queries is None:
        queries = DEFAULT_QUERIES

    # Run comparison
    results = []

    for i, q_data in enumerate(queries, 1):
        query = q_data["query"]
        query_type = q_data["type"]

        print(f"\n🔍 [{i}/{len(queries)}] {query[:50]}...")

        result = compare_retrieval_methods(query, hybrid_retriever)
        result["query_type"] = query_type
        results.append(result)

        print(f"   Hybrid: {result['hybrid_time_ms']:.1f}ms, div={result['hybrid_diversity']:.3f}")
        print(
            f"   Semantic: {result['semantic_time_ms']:.1f}ms, div={result['semantic_diversity']:.3f}"
        )
        print(f"   Improvement: {result['diversity_improvement']:+.3f}")

    # Create DataFrame
    df = pd.DataFrame(results)

    # Save detailed results
    csv_path = os.path.join(output_dir, "hybrid_vs_semantic_comparison.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n💾 Saved: {csv_path}")

    # Generate summary
    summary_path = os.path.join(output_dir, "hybrid_vs_semantic_summary.txt")
    with open(summary_path, "w") as f:
        f.write("HYBRID VS SEMANTIC RETRIEVAL COMPARISON\n")
        f.write("=" * 60 + "\n\n")

        f.write("OVERALL METRICS\n")
        f.write("-" * 60 + "\n")
        f.write(f"Queries evaluated: {len(df)}\n\n")

        f.write("Average Times:\n")
        f.write(f"  Hybrid (RRF):  {df['hybrid_time_ms'].mean():.2f}ms\n")
        f.write(f"  Semantic-only: {df['semantic_time_ms'].mean():.2f}ms\n")
        f.write(f"  Lexical-only:  {df['lexical_time_ms'].mean():.2f}ms\n\n")

        f.write("Average Diversity:\n")
        f.write(f"  Hybrid (RRF):  {df['hybrid_diversity'].mean():.3f}\n")
        f.write(f"  Semantic-only: {df['semantic_diversity'].mean():.3f}\n")
        f.write(f"  Lexical-only:  {df['lexical_diversity'].mean():.3f}\n\n")

        f.write("Diversity Improvement (Hybrid vs Semantic):\n")
        f.write(f"  Mean:   {df['diversity_improvement'].mean():+.3f}\n")
        f.write(f"  Median: {df['diversity_improvement'].median():+.3f}\n")
        f.write(f"  Min:    {df['diversity_improvement'].min():+.3f}\n")
        f.write(f"  Max:    {df['diversity_improvement'].max():+.3f}\n\n")

        f.write("BY QUERY TYPE\n")
        f.write("-" * 60 + "\n")

        for query_type in df["query_type"].unique():
            type_df = df[df["query_type"] == query_type]
            f.write(f"\n{query_type.upper()}:\n")
            f.write(f"  Queries: {len(type_df)}\n")
            f.write(f"  Avg Hybrid Time: {type_df['hybrid_time_ms'].mean():.2f}ms\n")
            f.write(f"  Avg Hybrid Diversity: {type_df['hybrid_diversity'].mean():.3f}\n")
            f.write(f"  Avg Improvement: {type_df['diversity_improvement'].mean():+.3f}\n")

    print(f"💾 Saved: {summary_path}")

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare hybrid vs semantic retrieval")
    parser.add_argument("--document", type=str, required=True, help="Path to PDF document")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument(
        "--model", type=str, default="S-PubMedBert-MS-MARCO", help="Embedding model"
    )

    args = parser.parse_args()

    run_hybrid_comparison(
        document_path=args.document, embedding_model=args.model, output_dir=args.output
    )
