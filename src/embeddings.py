"""
Embedding Model Management
==========================

Handles loading and configuration of embedding models, including
medical-specialized models for clinical trial documentation.

Supported Model Types:
- General Purpose: all-mpnet-base-v2, all-MiniLM-L6-v2
- Medical/Scientific: S-PubMedBert-MS-MARCO, BioSimCSE-BioLinkBERT, BioBERT
- Lightweight: bert-tiny-mnli
"""

import logging
from typing import Any

from langchain_huggingface import HuggingFaceEmbeddings

from .config import EMBEDDING_MODELS

logger = logging.getLogger(__name__)


def get_model_info(model_key: str) -> dict[str, Any] | None:
    """
    Get configuration information for an embedding model.

    Args:
        model_key: Key identifier for the model (e.g., "S-PubMedBert-MS-MARCO")

    Returns:
        Dictionary with model configuration or None if not found
    """
    return EMBEDDING_MODELS.get(model_key)


def list_available_models() -> dict[str, dict[str, Any]]:
    """
    Get all available embedding models grouped by type.

    Returns:
        Dictionary with model types as keys and list of model configs as values
    """
    grouped = {
        "general": [],
        "medical": [],
        "lightweight": [],
    }

    for key, config in EMBEDDING_MODELS.items():
        model_type = config.get("type", "general")
        grouped[model_type].append({"key": key, **config})

    return grouped


def create_embedder(
    model_key: str, device: str = "cpu", normalize_embeddings: bool = True, batch_size: int = 32
) -> HuggingFaceEmbeddings | None:
    """
    Create a HuggingFace embedder with proper error handling.

    Handles medical models that may require fallbacks and provides
    consistent configuration across all model types.

    Args:
        model_key: Key identifier for the model (e.g., "S-PubMedBert-MS-MARCO")
        device: Device to load model on ("cpu" or "cuda")
        normalize_embeddings: Whether to L2-normalize embeddings
        batch_size: Batch size for encoding

    Returns:
        HuggingFaceEmbeddings instance or None if creation fails

    Example:
        >>> embedder = create_embedder("S-PubMedBert-MS-MARCO")
        >>> embeddings = embedder.embed_documents(["Sample text"])
    """
    model_config = EMBEDDING_MODELS.get(model_key, {})
    model_name = model_config.get("name", model_key)
    model_type = model_config.get("type", "general")

    logger.info(f"Loading embedding model: {model_name} (type: {model_type})")

    encode_kwargs = {
        "normalize_embeddings": normalize_embeddings,
        "batch_size": batch_size,
    }

    model_kwargs = {
        "device": device,
    }

    try:
        # Attempt to load the primary model
        embedder = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )

        # Test the embedder with a simple query
        _ = embedder.embed_query("test")

        logger.info(f"Successfully loaded {model_key}")
        return embedder

    except Exception as e:
        logger.warning(f"Failed to load {model_name}: {e}")

        # Try fallback model if configured
        fallback = model_config.get("fallback")
        if fallback:
            logger.info(f"Attempting fallback model: {fallback}")
            try:
                embedder = HuggingFaceEmbeddings(
                    model_name=fallback,
                    model_kwargs=model_kwargs,
                    encode_kwargs=encode_kwargs,
                )
                _ = embedder.embed_query("test")
                logger.info(f"Successfully loaded fallback: {fallback}")
                return embedder
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")

        # Last resort: MiniLM
        logger.info("Attempting last-resort fallback: all-MiniLM-L6-v2")
        try:
            embedder = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs=model_kwargs,
                encode_kwargs=encode_kwargs,
            )
            return embedder
        except Exception as final_error:
            logger.error(f"All embedding model attempts failed: {final_error}")
            return None


def get_embedding_dimensions(model_key: str) -> int:
    """
    Get the embedding dimensions for a model.

    Args:
        model_key: Key identifier for the model

    Returns:
        Number of dimensions (default 384 if unknown)
    """
    config = EMBEDDING_MODELS.get(model_key, {})
    return config.get("dimensions", 384)


def get_recommended_model(document_type: str = "clinical") -> str:
    """
    Get the recommended embedding model for a document type.

    Args:
        document_type: Type of document ("clinical", "general", "fast")

    Returns:
        Model key string
    """
    recommendations = {
        "clinical": "S-PubMedBert-MS-MARCO",
        "medical": "S-PubMedBert-MS-MARCO",
        "biomedical": "BioSimCSE-BioLinkBERT",
        "general": "all-mpnet-base-v2",
        "fast": "all-MiniLM-L6-v2",
        "lightweight": "bert-tiny-mnli",
    }

    return recommendations.get(document_type.lower(), "all-mpnet-base-v2")
