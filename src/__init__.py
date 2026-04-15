"""
Adaptive RAG Clinical Assistant
===============================

A Retrieval-Augmented Generation system for clinical trial documentation
with adaptive response generation based on user expertise levels.

Key Features:
- Reciprocal Rank Fusion (RRF) for hybrid retrieval
- 5 expertise-based personas (Novice, Intermediate, Expert, Regulatory, Executive)
- 9 query type classifications
- Medical-specialized embedding models
"""

from .config import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, EMBEDDING_MODELS
from .embeddings import create_embedder, get_model_info
from .personas import ResponseConfig, UserType, detect_user_type, get_response_config
from .prompts import ResponseStyler, build_adaptive_prompt
from .query_classifier import QueryType, classify_query
from .retrieval import HybridRetriever, ReciprocalRankFusion
from .utils import calculate_diversity_score, calculate_text_hash

__version__ = "2.0.0"
__author__ = "Khalid Siddiqui"

__all__ = [
    # Config
    "EMBEDDING_MODELS",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    # Personas
    "UserType",
    "ResponseConfig",
    "detect_user_type",
    "get_response_config",
    # Query Classification
    "QueryType",
    "classify_query",
    # Retrieval
    "ReciprocalRankFusion",
    "HybridRetriever",
    # Embeddings
    "create_embedder",
    "get_model_info",
    # Prompts
    "ResponseStyler",
    "build_adaptive_prompt",
    # Utils
    "calculate_diversity_score",
    "calculate_text_hash",
]
