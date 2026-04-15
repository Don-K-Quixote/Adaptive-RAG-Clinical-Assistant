"""
OCR Retrieval Quality Evaluation
==================================

Evaluates retrieval quality on documents that were ingested via OCR compared
to documents with a native text layer. This closes the gap identified in the
pipeline review: OCR-extracted text was never included in any evaluation module.

The module:
1. Ingests a PDF using DocumentIngester (which applies OCR to scanned pages).
2. Classifies each chunk as TEXT_NATIVE or OCR-extracted based on metadata.
3. Runs a set of benchmark queries against the hybrid retriever.
4. For each retrieved result, records whether the source chunk came from an
   OCR page or a native-text page.
5. Reports per-source-type retrieval metrics: count, diversity, RRF scores,
   and retrieval latency.

Output:
- results/ocr_retrieval_quality.csv
- results/ocr_retrieval_quality_summary.txt
"""

import os
import sys
from pathlib import Path

import pandas as pd
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    HNSW_COLLECTION_METADATA,
)
from src.embeddings import create_embedder
from src.ingestion import DocumentIngester
from src.retrieval import HybridRetriever
from src.utils import calculate_diversity_score

DEFAULT_QUERIES = [
    {"query": "What are the RECIST 1.1 criteria for target lesion measurement?", "type": "medical"},
    {"query": "Define progressive disease in oncology imaging", "type": "medical"},
    {"query": "Baseline imaging schedule and timing requirements", "type": "procedural"},
    {"query": "How are non-target lesions assessed at follow-up?", "type": "medical"},
    {"query": "CT scan quality control procedures", "type": "procedural"},
    {"query": "What is the definition of complete response?", "type": "medical"},
    {"query": "Lymph node size threshold for target lesion classification", "type": "medical"},
    {"query": "Adverse event reporting requirements for imaging agents", "type": "procedural"},
]


def _chunk_source_type(chunk) -> str:
    """Return 'ocr' if the chunk came from an OCR page, else 'text_native'."""
    classification = chunk.metadata.get("classification", "text_native")
    # DocumentIngester sets classification to 'needs_ocr' for OCR-processed pages
    if classification == "needs_ocr":
        return "ocr"
    return "text_native"


def evaluate_ocr_retrieval(
    document_path: str,
    queries: list[dict] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    output_dir: str = "results",
    top_k: int = 5,
    ocr_provider: str = "surya",
    openai_api_key: str | None = None,
) -> pd.DataFrame:
    """
    Run retrieval quality evaluation across OCR and native-text chunks.

    Args:
        document_path: Path to the PDF document (may contain scanned pages).
        queries: List of query dicts with 'query' and 'type' keys.
            Defaults to DEFAULT_QUERIES.
        embedding_model: Embedding model key from src/config.py.
        output_dir: Directory for output CSV and summary files.
        top_k: Number of results to retrieve per query.
        ocr_provider: OCR backend to use ('surya' or 'openai').
        openai_api_key: Required when ocr_provider='openai'.

    Returns:
        DataFrame with per-query per-source-type retrieval metrics.
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading and ingesting document: {document_path}")
    ingester = DocumentIngester(
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        ocr_provider=ocr_provider,
        openai_api_key=openai_api_key or "",
    )
    chunks = ingester.ingest(document_path)

    # Summarise chunk composition
    ocr_chunks = [c for c in chunks if _chunk_source_type(c) == "ocr"]
    native_chunks = [c for c in chunks if _chunk_source_type(c) == "text_native"]
    print(
        f"Ingested {len(chunks)} chunks total: "
        f"{len(native_chunks)} text-native, {len(ocr_chunks)} OCR-extracted."
    )

    if not ocr_chunks:
        print(
            "WARNING: No OCR chunks found. The document may be fully text-native. "
            "OCR retrieval quality metrics will not be meaningful."
        )

    # Build vector store and BM25 index
    print(f"Building embeddings with {embedding_model}...")
    embedder = create_embedder(embedding_model)

    persist_dir = os.path.join(output_dir, f"chroma_ocr_eval_{embedding_model.replace('/', '_')}")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=persist_dir,
        collection_metadata=HNSW_COLLECTION_METADATA,
    )

    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = top_k * 2

    hybrid_retriever = HybridRetriever(
        vectordb=vectordb,
        bm25_retriever=bm25_retriever,
        top_k=top_k,
    )

    if queries is None:
        queries = DEFAULT_QUERIES

    results = []
    for i, q_data in enumerate(queries, 1):
        query = q_data["query"]
        query_type = q_data["type"]

        print(f"\n[{i}/{len(queries)}] {query[:60]}...")

        retrieval = hybrid_retriever.retrieve_with_metadata(query, top_k=top_k)
        docs = retrieval["documents"]
        rrf_results = retrieval["rrf_results"]
        timing = retrieval["timing"]

        if not docs:
            print("  No results returned.")
            results.append(
                {
                    "query": query,
                    "query_type": query_type,
                    "total_retrieved": 0,
                    "ocr_retrieved": 0,
                    "native_retrieved": 0,
                    "ocr_fraction": 0.0,
                    "overall_diversity": 0.0,
                    "ocr_diversity": 0.0,
                    "native_diversity": 0.0,
                    "avg_rrf_score_ocr": None,
                    "avg_rrf_score_native": None,
                    "retrieval_total_ms": timing["total_ms"],
                }
            )
            continue

        # Annotate each result with its source type
        annotated = [
            {
                "doc": rrf.document,
                "rrf_score": rrf.rrf_score,
                "source_type": _chunk_source_type(rrf.document),
            }
            for rrf in rrf_results
        ]

        ocr_results = [a for a in annotated if a["source_type"] == "ocr"]
        native_results = [a for a in annotated if a["source_type"] == "text_native"]

        ocr_docs = [a["doc"] for a in ocr_results]
        native_docs = [a["doc"] for a in native_results]

        overall_diversity = calculate_diversity_score(docs)
        ocr_diversity = calculate_diversity_score(ocr_docs) if ocr_docs else 0.0
        native_diversity = calculate_diversity_score(native_docs) if native_docs else 0.0

        avg_rrf_ocr = (
            sum(a["rrf_score"] for a in ocr_results) / len(ocr_results) if ocr_results else None
        )
        avg_rrf_native = (
            sum(a["rrf_score"] for a in native_results) / len(native_results)
            if native_results
            else None
        )

        row = {
            "query": query,
            "query_type": query_type,
            "total_retrieved": len(docs),
            "ocr_retrieved": len(ocr_results),
            "native_retrieved": len(native_results),
            "ocr_fraction": len(ocr_results) / len(docs),
            "overall_diversity": round(overall_diversity, 4),
            "ocr_diversity": round(ocr_diversity, 4),
            "native_diversity": round(native_diversity, 4),
            "avg_rrf_score_ocr": round(avg_rrf_ocr, 6) if avg_rrf_ocr is not None else None,
            "avg_rrf_score_native": (
                round(avg_rrf_native, 6) if avg_rrf_native is not None else None
            ),
            "retrieval_total_ms": timing["total_ms"],
        }
        results.append(row)

        print(
            f"  Retrieved {len(docs)} docs: "
            f"{len(native_results)} text-native, {len(ocr_results)} OCR. "
            f"Diversity={overall_diversity:.3f}. "
            f"Latency={timing['total_ms']:.1f}ms."
        )

    df = pd.DataFrame(results)

    # Save CSV
    csv_path = os.path.join(output_dir, "ocr_retrieval_quality.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nSaved: {csv_path}")

    # Save summary
    summary_path = os.path.join(output_dir, "ocr_retrieval_quality_summary.txt")
    with open(summary_path, "w") as f:
        f.write("OCR RETRIEVAL QUALITY EVALUATION\n")
        f.write("=" * 60 + "\n\n")

        f.write("DOCUMENT COMPOSITION\n")
        f.write("-" * 60 + "\n")
        f.write(f"Total chunks:        {len(chunks)}\n")
        f.write(f"Text-native chunks:  {len(native_chunks)}\n")
        f.write(f"OCR chunks:          {len(ocr_chunks)}\n\n")

        f.write("RETRIEVAL METRICS (averaged across queries)\n")
        f.write("-" * 60 + "\n")
        f.write(f"Queries evaluated:   {len(df)}\n")
        f.write(f"Avg total retrieved: {df['total_retrieved'].mean():.1f}\n")
        f.write(f"Avg OCR retrieved:   {df['ocr_retrieved'].mean():.1f}\n")
        f.write(f"Avg native retrieved:{df['native_retrieved'].mean():.1f}\n")
        f.write(f"Avg OCR fraction:    {df['ocr_fraction'].mean():.1%}\n\n")

        f.write("DIVERSITY SCORES\n")
        f.write("-" * 60 + "\n")
        f.write(f"Overall:             {df['overall_diversity'].mean():.4f}\n")
        f.write(f"OCR chunks only:     {df['ocr_diversity'].mean():.4f}\n")
        f.write(f"Native chunks only:  {df['native_diversity'].mean():.4f}\n\n")

        f.write("RRF SCORES\n")
        f.write("-" * 60 + "\n")
        ocr_scores = df["avg_rrf_score_ocr"].dropna()
        native_scores = df["avg_rrf_score_native"].dropna()
        if len(ocr_scores):
            f.write(f"Avg RRF score (OCR):    {ocr_scores.mean():.6f}\n")
        else:
            f.write("Avg RRF score (OCR):    N/A (no OCR chunks retrieved)\n")
        if len(native_scores):
            f.write(f"Avg RRF score (native): {native_scores.mean():.6f}\n")
        else:
            f.write("Avg RRF score (native): N/A\n")

        f.write("\nLATENCY\n")
        f.write("-" * 60 + "\n")
        f.write(f"Avg retrieval latency: {df['retrieval_total_ms'].mean():.2f}ms\n")

        f.write("\nPER QUERY TYPE\n")
        f.write("-" * 60 + "\n")
        for qt in df["query_type"].unique():
            sub = df[df["query_type"] == qt]
            f.write(f"\n{qt.upper()}:\n")
            f.write(f"  Queries:           {len(sub)}\n")
            f.write(f"  Avg OCR fraction:  {sub['ocr_fraction'].mean():.1%}\n")
            f.write(f"  Avg diversity:     {sub['overall_diversity'].mean():.4f}\n")

    print(f"Saved: {summary_path}")
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate retrieval quality on OCR-extracted text")
    parser.add_argument("--document", type=str, required=True, help="Path to PDF document")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument(
        "--model", type=str, default="S-PubMedBert-MS-MARCO", help="Embedding model"
    )
    parser.add_argument(
        "--ocr-provider", type=str, default="surya", choices=["surya", "openai"],
        help="OCR provider to use for scanned pages"
    )
    parser.add_argument("--openai-api-key", type=str, default=None, help="OpenAI API key")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results per query")

    args = parser.parse_args()

    evaluate_ocr_retrieval(
        document_path=args.document,
        embedding_model=args.model,
        output_dir=args.output,
        top_k=args.top_k,
        ocr_provider=args.ocr_provider,
        openai_api_key=args.openai_api_key,
    )
