"""
End-to-End Latency Measurement
==============================

Measures latency across the entire pipeline:
- Document loading
- Embedding creation
- Retrieval (semantic, lexical, hybrid)
- Response generation

Output:
- results/latency_results.csv
- results/latency_summary.txt
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import find_dotenv, load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_LLM_MODEL,
    HNSW_COLLECTION_METADATA,
    LATENCY_SLA,
)
from src.embeddings import create_embedder
from src.personas import UserType, get_response_config
from src.prompts import build_adaptive_prompt
from src.query_classifier import classify_query
from src.retrieval import HybridRetriever
from src.utils import save_run_snapshot

load_dotenv(find_dotenv())


DEFAULT_QUERIES = [
    "What is RECIST 1.1?",
    "How to measure target lesions?",
    "Baseline imaging requirements",
    "What defines progressive disease?",
    "Safety reporting procedures",
    "Define complete response in oncology imaging",
    "Lymph node size threshold for target lesion classification",
    "CT scan quality control requirements",
    "Compare CT and MRI for tumour assessment",
    "Adverse event reporting requirements for imaging agents",
]


def measure_pipeline_latency(
    query: str,
    hybrid_retriever: HybridRetriever,
    llm: ChatOpenAI,
    user_type: UserType = UserType.INTERMEDIATE,
    num_runs: int = 3,
) -> dict:
    """
    Measure latency for a single query across multiple runs.

    Args:
        query: Test query
        hybrid_retriever: Configured HybridRetriever
        llm: Language model
        user_type: User persona for response generation
        num_runs: Number of runs for averaging

    Returns:
        Dictionary with latency metrics
    """
    retrieval_times = []
    generation_times = []
    total_times = []

    query_type = classify_query(query)
    config = get_response_config(user_type, query_type.value)

    for _run in range(num_runs):
        # Retrieval timing
        start_retrieval = time.time()
        documents = hybrid_retriever.retrieve(query, top_k=5)
        retrieval_time = (time.time() - start_retrieval) * 1000
        retrieval_times.append(retrieval_time)

        # Prompt building (usually negligible)
        prompt = build_adaptive_prompt(documents, query, config)

        # Generation timing
        start_generation = time.time()
        response = llm.invoke(prompt)
        generation_time = (time.time() - start_generation) * 1000
        generation_times.append(generation_time)

        total_times.append(retrieval_time + generation_time)

    return {
        "query": query,
        "query_type": query_type.value,
        "user_type": user_type.value,
        "num_runs": num_runs,
        # Retrieval metrics
        "retrieval_mean_ms": np.mean(retrieval_times),
        "retrieval_std_ms": np.std(retrieval_times),
        "retrieval_min_ms": np.min(retrieval_times),
        "retrieval_max_ms": np.max(retrieval_times),
        # Generation metrics
        "generation_mean_ms": np.mean(generation_times),
        "generation_std_ms": np.std(generation_times),
        "generation_min_ms": np.min(generation_times),
        "generation_max_ms": np.max(generation_times),
        # Total metrics
        "total_mean_ms": np.mean(total_times),
        "total_std_ms": np.std(total_times),
        # Response info
        "response_length": len(response.content),
        "response_words": len(response.content.split()),
    }


def run_latency_measurement(
    document_path: str,
    queries: list[str] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    llm_model: str = DEFAULT_LLM_MODEL,
    num_runs: int = 3,
    output_dir: str = "results",
) -> pd.DataFrame:
    """
    Run comprehensive latency measurement.

    Args:
        document_path: Path to PDF document
        queries: List of test queries
        embedding_model: Embedding model to use
        llm_model: LLM for response generation
        num_runs: Number of runs per query for averaging
        output_dir: Directory for output files

    Returns:
        DataFrame with latency results
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"📄 Loading document: {document_path}")

    # Measure document loading time
    start_load = time.time()
    loader = PyPDFLoader(document_path)
    pages = loader.load()
    load_time = (time.time() - start_load) * 1000
    print(f"   Document load time: {load_time:.2f}ms")

    # Measure chunking time
    start_chunk = time.time()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)
    chunk_time = (time.time() - start_chunk) * 1000
    print(f"   Chunking time: {chunk_time:.2f}ms ({len(chunks)} chunks)")

    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = i

    # Measure embedding/indexing time
    print(f"🔧 Creating embeddings with {embedding_model}...")
    start_embed = time.time()
    embedder = create_embedder(embedding_model)
    embed_load_time = (time.time() - start_embed) * 1000
    print(f"   Embedder load time: {embed_load_time:.2f}ms")

    persist_dir = os.path.join(output_dir, f"chroma_latency_{embedding_model.replace('/', '_')}")

    start_index = time.time()
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=persist_dir,
        collection_metadata=HNSW_COLLECTION_METADATA,
    )
    index_time = (time.time() - start_index) * 1000
    print(f"   Indexing time: {index_time:.2f}ms")

    # Create BM25 retriever
    start_bm25 = time.time()
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 10
    bm25_time = (time.time() - start_bm25) * 1000
    print(f"   BM25 index time: {bm25_time:.2f}ms")

    # Create hybrid retriever
    hybrid_retriever = HybridRetriever(vectordb=vectordb, bm25_retriever=bm25_retriever, top_k=5)

    # Create LLM
    llm = ChatOpenAI(model=llm_model, temperature=0)

    # Use default queries if not provided
    if queries is None:
        queries = DEFAULT_QUERIES

    # Measure query latencies
    print(f"\n⏱️ Measuring latencies ({num_runs} runs per query)...")

    results = []
    wall_start = time.time()

    for i, query in enumerate(queries, 1):
        print(f"\n🔍 [{i}/{len(queries)}] {query[:50]}...")

        result = measure_pipeline_latency(
            query=query, hybrid_retriever=hybrid_retriever, llm=llm, num_runs=num_runs
        )
        results.append(result)

        retrieval_sla = (
            "PASS" if result["retrieval_mean_ms"] <= LATENCY_SLA["retrieval_ms"] else "FAIL"
        )
        generation_sla = (
            "PASS" if result["generation_mean_ms"] <= LATENCY_SLA["generation_ms"] else "FAIL"
        )
        total_sla = "PASS" if result["total_mean_ms"] <= LATENCY_SLA["total_ms"] else "FAIL"

        print(
            f"   Retrieval: {result['retrieval_mean_ms']:.1f}ms ± {result['retrieval_std_ms']:.1f}ms [{retrieval_sla}]"
        )
        print(
            f"   Generation: {result['generation_mean_ms']:.1f}ms ± {result['generation_std_ms']:.1f}ms [{generation_sla}]"
        )
        print(f"   Total: {result['total_mean_ms']:.1f}ms [{total_sla}]")

    wall_elapsed_s = time.time() - wall_start
    throughput_qps = len(queries) / wall_elapsed_s if wall_elapsed_s > 0 else 0.0

    # Create DataFrame
    df = pd.DataFrame(results)

    # Save results
    csv_path = os.path.join(output_dir, "latency_results.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n💾 Saved: {csv_path}")

    # Generate summary
    summary_path = os.path.join(output_dir, "latency_summary.txt")

    def _sla_tag(observed: float, threshold: float) -> str:
        return "PASS" if observed <= threshold else "FAIL"

    avg_retrieval = df["retrieval_mean_ms"].mean()
    avg_generation = df["generation_mean_ms"].mean()
    avg_total = df["total_mean_ms"].mean()

    with open(summary_path, "w") as f:
        f.write("LATENCY MEASUREMENT SUMMARY\n")
        f.write("=" * 60 + "\n\n")

        f.write("SETUP TIMES (One-time)\n")
        f.write("-" * 60 + "\n")
        f.write(f"Document loading:    {load_time:.2f}ms\n")
        f.write(f"Chunking:            {chunk_time:.2f}ms\n")
        f.write(f"Embedder loading:    {embed_load_time:.2f}ms\n")
        f.write(f"Vector indexing:     {index_time:.2f}ms\n")
        f.write(f"BM25 indexing:       {bm25_time:.2f}ms\n")
        f.write(
            f"Total setup:         {load_time + chunk_time + embed_load_time + index_time + bm25_time:.2f}ms\n\n"
        )

        f.write("QUERY TIMES (Per-query)\n")
        f.write("-" * 60 + "\n")
        f.write(f"Queries tested:      {len(df)}\n")
        f.write(f"Runs per query:      {num_runs}\n\n")

        f.write("Retrieval:\n")
        f.write(
            f"  Mean:   {avg_retrieval:.2f}ms  [SLA {LATENCY_SLA['retrieval_ms']:.0f}ms → {_sla_tag(avg_retrieval, LATENCY_SLA['retrieval_ms'])}]\n"
        )
        f.write(f"  Min:    {df['retrieval_min_ms'].min():.2f}ms\n")
        f.write(f"  Max:    {df['retrieval_max_ms'].max():.2f}ms\n\n")

        f.write("Generation:\n")
        f.write(
            f"  Mean:   {avg_generation:.2f}ms  [SLA {LATENCY_SLA['generation_ms']:.0f}ms → {_sla_tag(avg_generation, LATENCY_SLA['generation_ms'])}]\n"
        )
        f.write(f"  Min:    {df['generation_min_ms'].min():.2f}ms\n")
        f.write(f"  Max:    {df['generation_max_ms'].max():.2f}ms\n\n")

        f.write("Total (Retrieval + Generation):\n")
        f.write(
            f"  Mean:   {avg_total:.2f}ms  [SLA {LATENCY_SLA['total_ms']:.0f}ms → {_sla_tag(avg_total, LATENCY_SLA['total_ms'])}]\n"
        )
        f.write(f"  Min:    {df['total_mean_ms'].min():.2f}ms\n")
        f.write(f"  Max:    {df['total_mean_ms'].max():.2f}ms\n\n")

        f.write("THROUGHPUT\n")
        f.write("-" * 60 + "\n")
        f.write(f"Sequential queries:  {len(df)}\n")
        f.write(f"Wall time (s):       {wall_elapsed_s:.2f}s\n")
        f.write(f"Throughput:          {throughput_qps:.3f} queries/sec\n\n")

        f.write("CONFIGURATION\n")
        f.write("-" * 60 + "\n")
        f.write(f"Embedding model:     {embedding_model}\n")
        f.write(f"LLM model:           {llm_model}\n")
        f.write(f"Document:            {document_path}\n")
        f.write(f"Chunks:              {len(chunks)}\n")
        f.write(f"Timestamp:           {datetime.now().isoformat()}\n")

    print(f"💾 Saved: {summary_path}")

    # Snapshot results for run versioning
    snapshot_dir = save_run_snapshot(
        [csv_path, summary_path],
        os.path.join(output_dir, "history"),
    )
    print(f"📦 Snapshot: {snapshot_dir}")

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Measure pipeline latency")
    parser.add_argument("--document", type=str, required=True, help="Path to PDF document")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument(
        "--model", type=str, default="S-PubMedBert-MS-MARCO", help="Embedding model"
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of runs per query")

    args = parser.parse_args()

    run_latency_measurement(
        document_path=args.document,
        embedding_model=args.model,
        num_runs=args.runs,
        output_dir=args.output,
    )
