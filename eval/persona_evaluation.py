"""
Persona-Based Response Evaluation
=================================

Evaluates response quality across different user personas:
- Novice, Intermediate, Expert, Regulatory, Executive

Output:
- results/persona_responses.json
- results/persona_responses_formatted.html
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

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
)
from src.embeddings import create_embedder
from src.faithfulness import FAITHFULNESS_WARNING_THRESHOLD, FaithfulnessChecker
from src.personas import UserType, get_response_config
from src.prompts import build_adaptive_prompt
from src.query_classifier import classify_query
from src.retrieval import HybridRetriever
from src.utils import save_run_snapshot

try:
    import textstat

    _TEXTSTAT_AVAILABLE = True
except ImportError:
    _TEXTSTAT_AVAILABLE = False

load_dotenv(find_dotenv())


# Test queries for persona evaluation
DEFAULT_QUERIES = [
    "What is RECIST 1.1?",
    "How do I measure target lesions?",
    "What are the compliance requirements for imaging?",
    "Compare CT and MRI for tumor assessment",
    "What is the imaging schedule?",
]


def evaluate_persona_responses(
    query: str,
    hybrid_retriever: HybridRetriever,
    llm: ChatOpenAI,
    top_k: int = 5,
    embedder=None,
) -> dict:
    """
    Generate responses for the same query across all personas.

    Args:
        query: The test query
        hybrid_retriever: Configured HybridRetriever
        llm: Language model for response generation
        top_k: Number of documents to retrieve
        embedder: Optional HuggingFaceEmbeddings instance for faithfulness scoring.
            When provided, FaithfulnessChecker scores each response against the
            retrieved context. Omit to skip faithfulness scoring.

    Returns:
        Dictionary with responses for each persona, including optional readability
        and faithfulness quality metrics per response.
    """
    # Retrieve documents once (same context for all personas)
    documents = hybrid_retriever.retrieve(query, top_k=top_k)

    # Classify query type
    query_type = classify_query(query)

    # Initialise faithfulness checker once per query if embedder available
    faithfulness_checker = FaithfulnessChecker(embedder) if embedder is not None else None

    responses = {}

    for user_type in UserType:
        # Get response configuration for this persona
        config = get_response_config(user_type, query_type.value)

        # Build adaptive prompt
        prompt = build_adaptive_prompt(documents, query, config)

        # Generate response
        start_time = time.time()
        response = llm.invoke(prompt)
        generation_time = (time.time() - start_time) * 1000

        text = response.content

        # Readability metrics (textstat; gracefully skipped if not installed)
        if _TEXTSTAT_AVAILABLE:
            readability_metrics = {
                "flesch_reading_ease": round(textstat.flesch_reading_ease(text), 2),
                "flesch_kincaid_grade": round(textstat.flesch_kincaid_grade(text), 2),
                "gunning_fog": round(textstat.gunning_fog(text), 2),
            }
        else:
            readability_metrics = {
                "flesch_reading_ease": None,
                "flesch_kincaid_grade": None,
                "gunning_fog": None,
            }

        # Faithfulness scoring
        if faithfulness_checker is not None:
            faith_result = faithfulness_checker.check(text, documents)
            faithfulness_metrics = {
                "faithfulness_score": round(faith_result.score, 4),
                "faithfulness_warning": faith_result.score < FAITHFULNESS_WARNING_THRESHOLD,
                "faithfulness_low_confidence_count": len(faith_result.low_confidence_sentences),
                "faithfulness_latency_ms": round(faith_result.latency_ms, 2),
            }
        else:
            faithfulness_metrics = {
                "faithfulness_score": None,
                "faithfulness_warning": None,
                "faithfulness_low_confidence_count": None,
                "faithfulness_latency_ms": None,
            }

        responses[user_type.value] = {
            "response": text,
            "config": {
                "user_type": user_type.value,
                "query_type": query_type.value,
                "detail_level": config.detail_level,
                "max_length": config.max_length,
                "use_tables": config.use_tables,
                "include_definitions": config.include_definitions,
                "include_key_takeaway": config.include_key_takeaway,
                "include_executive_summary": config.include_executive_summary,
            },
            "generation_time_ms": generation_time,
            "response_length": len(text),
            "word_count": len(text.split()),
            **readability_metrics,
            **faithfulness_metrics,
        }

    return {
        "query": query,
        "query_type": query_type.value,
        "num_sources": len(documents),
        "responses": responses,
    }


def run_persona_evaluation(
    document_path: str,
    queries: list[str] | None = None,
    embedding_model: str = "S-PubMedBert-MS-MARCO",
    llm_model: str = DEFAULT_LLM_MODEL,
    output_dir: str = "results",
) -> list[dict]:
    """
    Run persona evaluation across multiple queries.

    Args:
        document_path: Path to PDF document
        queries: List of test queries
        embedding_model: Embedding model to use
        llm_model: LLM model for response generation
        output_dir: Directory for output files

    Returns:
        List of evaluation results
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

    persist_dir = os.path.join(output_dir, f"chroma_persona_{embedding_model.replace('/', '_')}")
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embedder,
        persist_directory=persist_dir,
        collection_metadata=HNSW_COLLECTION_METADATA,
    )

    # Create BM25 retriever
    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 5

    # Create hybrid retriever
    hybrid_retriever = HybridRetriever(vectordb=vectordb, bm25_retriever=bm25_retriever, top_k=5)

    # Create LLM
    llm = ChatOpenAI(model=llm_model, temperature=0)

    # Use default queries if not provided
    if queries is None:
        queries = DEFAULT_QUERIES

    # Evaluate each query
    all_results = []

    for i, query in enumerate(queries, 1):
        print(f"\n🔍 [{i}/{len(queries)}] Evaluating: {query[:50]}...")

        result = evaluate_persona_responses(query, hybrid_retriever, llm, embedder=embedder)
        result["timestamp"] = datetime.now().isoformat()
        all_results.append(result)

        # Print summary
        for persona, data in result["responses"].items():
            faith_str = ""
            if data.get("faithfulness_score") is not None:
                faith_str = f", faith={data['faithfulness_score']:.3f}"
            print(
                f"   {persona}: {data['word_count']} words, {data['generation_time_ms']:.0f}ms{faith_str}"
            )

    # Save JSON results
    json_path = os.path.join(output_dir, "persona_responses.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved: {json_path}")

    # Generate HTML report
    html_path = os.path.join(output_dir, "persona_responses_formatted.html")
    generate_html_report(all_results, html_path)
    print(f"💾 Saved: {html_path}")

    # Snapshot results for run versioning
    snapshot_dir = save_run_snapshot(
        [json_path, html_path],
        os.path.join(output_dir, "history"),
    )
    print(f"📦 Snapshot: {snapshot_dir}")

    return all_results


def generate_html_report(results: list[dict], output_path: str):
    """Generate an HTML report for persona responses."""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Persona Evaluation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .query-section { margin-bottom: 40px; border: 1px solid #ddd; padding: 20px; }
        .query-title { font-size: 18px; font-weight: bold; color: #333; }
        .persona { margin: 15px 0; padding: 15px; background: #f9f9f9; border-radius: 5px; }
        .persona-header { font-weight: bold; color: #0066cc; }
        .config { font-size: 12px; color: #666; }
        .response { margin-top: 10px; white-space: pre-wrap; }
        .stats { font-size: 12px; color: #888; margin-top: 5px; }
    </style>
</head>
<body>
    <h1>Persona Evaluation Report</h1>
"""

    for result in results:
        html += f"""
    <div class="query-section">
        <div class="query-title">Query: {result["query"]}</div>
        <div class="config">Query Type: {result["query_type"]} | Sources: {result["num_sources"]}</div>
"""
        for persona, data in result["responses"].items():
            html += f"""
        <div class="persona">
            <div class="persona-header">{persona.upper()}</div>
            <div class="config">Detail: {data["config"]["detail_level"]} | Max: {data["config"]["max_length"]} words</div>
            <div class="response">{data["response"][:1000]}{"..." if len(data["response"]) > 1000 else ""}</div>
            <div class="stats">{data["word_count"]} words | {data["generation_time_ms"]:.0f}ms</div>
        </div>
"""
        html += "    </div>\n"

    html += """
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate persona-based responses")
    parser.add_argument("--document", type=str, required=True, help="Path to PDF document")
    parser.add_argument("--output", type=str, default="results", help="Output directory")
    parser.add_argument(
        "--model", type=str, default="S-PubMedBert-MS-MARCO", help="Embedding model"
    )

    args = parser.parse_args()

    run_persona_evaluation(
        document_path=args.document, embedding_model=args.model, output_dir=args.output
    )
