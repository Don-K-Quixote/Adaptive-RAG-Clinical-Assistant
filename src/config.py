"""
Configuration and Constants
============================

Central configuration for embedding models, chunking parameters,
and retrieval settings.
"""

from typing import Any

# ==============================================================================
# CHUNKING DEFAULTS
# ==============================================================================

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]

# ==============================================================================
# RETRIEVAL DEFAULTS
# ==============================================================================

DEFAULT_TOP_K = 5
RRF_K_CONSTANT = 60  # Standard value from literature (Cormack et al., 2009)
DEFAULT_SEMANTIC_WEIGHT = 0.6
DEFAULT_BM25_WEIGHT = 0.4
# Minimum RRF score to include a result (None = no filtering)
DEFAULT_SCORE_THRESHOLD: float | None = None

# ==============================================================================
# CHROMADB HNSW CONFIGURATION
# ==============================================================================
# These parameters control ChromaDB's HNSW index quality and speed.
# Apply as collection_metadata when calling Chroma.from_documents().
#
#  hnsw:M               — bidirectional links per node; higher = more accurate
#                         but more memory. 16 is a strong default for RAG.
#  hnsw:construction_ef — beam width at index-build time; higher = better index
#                         quality. 200 is a solid production default.
#  hnsw:search_ef       — beam width at query time; higher = better recall.
#                         100 gives a good accuracy/speed trade-off.
#  hnsw:space           — distance metric; "cosine" matches how sentence-
#                         transformers are trained.
HNSW_COLLECTION_METADATA: dict[str, object] = {
    "hnsw:space": "cosine",
    "hnsw:M": 16,
    "hnsw:construction_ef": 200,
    "hnsw:search_ef": 100,
}

# ==============================================================================
# EMBEDDING MODEL CONFIGURATIONS
# ==============================================================================

EMBEDDING_MODELS: dict[str, dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # General Purpose Models
    # -------------------------------------------------------------------------
    "all-mpnet-base-v2": {
        "name": "sentence-transformers/all-mpnet-base-v2",
        "type": "general",
        "description": "High-quality general-purpose embeddings, good balance of speed and accuracy",
        "dimensions": 768,
        "max_seq_length": 384,
        "recommended_for": ["general documents", "mixed content"],
    },
    "all-MiniLM-L6-v2": {
        "name": "sentence-transformers/all-MiniLM-L6-v2",
        "type": "general",
        "description": "Fast general-purpose embeddings, optimized for speed",
        "dimensions": 384,
        "max_seq_length": 256,
        "recommended_for": ["rapid prototyping", "resource-constrained environments"],
    },
    # -------------------------------------------------------------------------
    # Medical/Scientific Models (Recommended for Clinical Documents)
    # -------------------------------------------------------------------------
    "S-PubMedBert-MS-MARCO": {
        "name": "pritamdeka/S-PubMedBert-MS-MARCO",
        "type": "medical",
        "description": "PubMedBERT fine-tuned on MS-MARCO, optimized for medical text retrieval",
        "dimensions": 768,
        "max_seq_length": 512,
        "recommended_for": ["clinical trials", "medical documentation", "IRC charters"],
    },
    "BioSimCSE-BioLinkBERT": {
        "name": "kamalkraj/BioSimCSE-BioLinkBERT-BASE",
        "type": "medical",
        "description": "Biomedical embeddings with contrastive learning, excellent for scientific text",
        "dimensions": 768,
        "max_seq_length": 512,
        "recommended_for": ["biomedical literature", "research protocols"],
    },
    "BioBERT": {
        "name": "dmis-lab/biobert-base-cased-v1.2",
        "type": "medical",
        "description": "BioBERT trained on PubMed abstracts and PMC full-text articles",
        "dimensions": 768,
        "max_seq_length": 512,
        "fallback": "sentence-transformers/all-MiniLM-L6-v2",
        "recommended_for": ["biomedical NLP", "scientific papers"],
    },
    # -------------------------------------------------------------------------
    # Lightweight Models
    # -------------------------------------------------------------------------
    "bert-tiny-mnli": {
        "name": "prajjwal1/bert-tiny-mnli",
        "type": "lightweight",
        "description": "Tiny BERT for fast inference, lower accuracy but minimal resources",
        "dimensions": 128,
        "max_seq_length": 512,
        "recommended_for": ["testing", "low-resource deployment"],
    },
}

# ==============================================================================
# LLM CONFIGURATIONS
# ==============================================================================

# LLM Provider options
LLM_PROVIDERS = ["OpenAI (Cloud)", "Ollama (Local)"]
DEFAULT_LLM_PROVIDER = "OpenAI (Cloud)"

# OpenAI Models (Cloud)
OPENAI_MODELS = {
    "gpt-4o-mini": {
        "description": "Fast & cost-effective, good for most queries",
        "context_window": 128000,
    },
    "gpt-4o": {
        "description": "Best quality, recommended for complex queries",
        "context_window": 128000,
    },
    "gpt-4": {
        "description": "High quality, reliable performance",
        "context_window": 8192,
    },
    "gpt-3.5-turbo": {
        "description": "Legacy model, fastest response time",
        "context_window": 16385,
    },
}

# Ollama Models (Local) - Verified working models
OLLAMA_MODELS = {
    "llama3.1:8b": {
        "description": "Meta's Llama 3.1 8B - Best general performance",
        "context_window": 8192,
        "vram_required": "~5GB",
    },
    "adrienbrault/biomistral-7b:Q4_K_M": {
        "description": "BioMistral 7B - Medical domain fine-tuned",
        "context_window": 32768,
        "vram_required": "~4.5GB",
    },
    "mistral:7b": {
        "description": "Mistral 7B - Fast and efficient",
        "context_window": 8192,
        "vram_required": "~4.5GB",
    },
    "gemma2:9b": {
        "description": "Google Gemma 2 9B - Strong reasoning",
        "context_window": 8192,
        "vram_required": "~5.5GB",
    },
    "phi3:mini": {
        "description": "Microsoft Phi-3 Mini - Fastest inference",
        "context_window": 4096,
        "vram_required": "~2.5GB",
    },
    "alibayram/medgemma:4b": {
        "description": "Google MedGemma 4B - Medical domain specialized (Gemma 3 variant)",
        "context_window": 8192,
        "vram_required": "~4-6GB (Q4)",
    },
}

# Legacy support
SUPPORTED_LLM_MODELS = list(OPENAI_MODELS.keys())
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LOCAL_MODEL = "llama3.1:8b"
DEFAULT_LLM_TEMPERATURE = 0

# ==============================================================================
# RESPONSE LENGTH LIMITS BY USER TYPE
# ==============================================================================

RESPONSE_LENGTH_LIMITS = {
    "novice": 300,
    "intermediate": 500,
    "expert": 1000,
    "regulatory": 800,
    "executive": 250,
}

# ==============================================================================
# FAITHFULNESS GATE
# ==============================================================================

# Hard block threshold — responses below this score are replaced with a refusal.
# Distinct from FAITHFULNESS_WARNING_THRESHOLD (0.45) which only shows a warning.
# Set lower than the warning threshold so only severely ungrounded responses are blocked.
FAITHFULNESS_BLOCK_THRESHOLD: float = 0.25

# ==============================================================================
# LATENCY SLA TARGETS
# ==============================================================================
# Pass/fail thresholds (milliseconds) for the Latency Measurement benchmark.
# Used by eval/latency_measurement.py: run_latency_measurement() to annotate
# each stage as PASS or FAIL in the latency_summary.txt report.
LATENCY_SLA: dict[str, float] = {
    "retrieval_ms": 500.0,  # max acceptable hybrid retrieval latency per query
    "generation_ms": 8000.0,  # max acceptable LLM generation latency per query
    "total_ms": 8000.0,  # max acceptable end-to-end (retrieval + generation) per query
}

# ==============================================================================
# COLOR CODING FOR RESPONSES
# ==============================================================================

RESPONSE_COLORS = {
    "critical": "#FF6B6B",
    "warning": "#FFA500",
    "normal": "#4ECDC4",
    "positive": "#95E1D3",
    "reference": "#A8DADC",
}
