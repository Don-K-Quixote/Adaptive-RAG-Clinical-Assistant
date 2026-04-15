"""
Utility Functions
=================

Common utility functions for the Adaptive RAG Clinical Assistant.
"""

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
from langchain_core.documents import Document


def calculate_text_hash(text: str) -> str:
    """
    Calculate MD5 hash of text for caching purposes.

    Args:
        text: Input text string

    Returns:
        MD5 hash as hexadecimal string
    """
    return hashlib.md5(text.encode()).hexdigest()


def calculate_diversity_score(documents: list[Document]) -> float:
    """
    Calculate diversity score for retrieved documents.

    Measures how diverse the retrieved results are based on:
    1. Page diversity: How many unique pages are represented
    2. Content overlap: How similar the content is between documents

    Higher scores indicate more diverse results (0.0 to 1.0).

    Args:
        documents: List of retrieved Document objects

    Returns:
        Float between 0.0 and 1.0 indicating diversity
    """
    if not documents:
        return 0.0

    if len(documents) == 1:
        return 1.0

    # Calculate page diversity
    pages = [doc.metadata.get("page", 0) for doc in documents]
    unique_pages = len(set(pages))
    page_diversity = unique_pages / len(documents)

    # Calculate content overlap (word-based Jaccard similarity)
    contents: list[set[str]] = [set(doc.page_content.lower().split()) for doc in documents]

    overlaps = []
    for i in range(len(contents)):
        for j in range(i + 1, len(contents)):
            if len(contents[i]) > 0 or len(contents[j]) > 0:
                intersection = len(contents[i] & contents[j])
                union = len(contents[i] | contents[j])
                overlap = intersection / union if union > 0 else 0
                overlaps.append(overlap)

    avg_overlap = np.mean(overlaps) if overlaps else 0
    content_diversity = 1 - avg_overlap

    # Combined score (weighted average)
    diversity = 0.4 * page_diversity + 0.6 * content_diversity

    return round(diversity, 3)


def deduplicate_documents(documents: list[Document]) -> list[Document]:
    """
    Remove duplicate documents based on content.

    Args:
        documents: List of Document objects

    Returns:
        List of unique Document objects (preserves order)
    """
    seen_content: set[str] = set()
    unique_docs = []

    for doc in documents:
        content_hash = calculate_text_hash(doc.page_content)
        if content_hash not in seen_content:
            seen_content.add(content_hash)
            unique_docs.append(doc)

    return unique_docs


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length with suffix.

    Args:
        text: Input text
        max_length: Maximum length before truncation
        suffix: String to append when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)].rsplit(" ", 1)[0] + suffix


def format_source_reference(document: Document, index: int = 1) -> str:
    """
    Format a document as a source reference string.

    Args:
        document: Document object
        index: Source index number

    Returns:
        Formatted string like "[Source 1: Page 5, Chunk 12]"
    """
    page = document.metadata.get("page", "N/A")
    chunk_id = document.metadata.get("chunk_id", "N/A")

    return f"[Source {index}: Page {page}, Chunk {chunk_id}]"


def estimate_tokens(text: str) -> int:
    """
    Rough estimation of token count for a text.

    Uses the approximation of ~4 characters per token for English text.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    return len(text) // 4


def save_run_snapshot(
    source_files: list,
    snapshot_dir: str | Path,
) -> Path:
    """
    Copy result files into a timestamped snapshot directory for run versioning.

    Creates ``snapshot_dir/<YYYYMMDDTHHMMSS>/`` and copies each existing file
    into it. Non-existent files are silently skipped.

    Args:
        source_files: List of file paths (str or Path) to snapshot.
        snapshot_dir: Parent directory for snapshot subdirectories
            (e.g. ``'results/history'``).

    Returns:
        Path to the created timestamped subdirectory.
    """
    snapshot_dir = Path(snapshot_dir)
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = snapshot_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    for src in source_files:
        src = Path(src)
        if src.exists():
            shutil.copy2(src, run_dir / src.name)

    return run_dir


def chunk_metadata_summary(documents: list[Document]) -> dict:
    """
    Generate summary statistics for retrieved chunks.

    Args:
        documents: List of Document objects

    Returns:
        Dictionary with summary statistics
    """
    if not documents:
        return {
            "count": 0,
            "unique_pages": 0,
            "avg_length": 0,
            "total_length": 0,
        }

    pages = [doc.metadata.get("page", 0) for doc in documents]
    lengths = [len(doc.page_content) for doc in documents]

    return {
        "count": len(documents),
        "unique_pages": len(set(pages)),
        "pages": sorted(set(pages)),
        "avg_length": int(np.mean(lengths)),
        "total_length": sum(lengths),
        "min_length": min(lengths),
        "max_length": max(lengths),
    }
