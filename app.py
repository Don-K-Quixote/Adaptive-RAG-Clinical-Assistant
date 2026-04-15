"""
Adaptive RAG Clinical Assistant - Main Application
===================================================

Streamlit-based web interface for the Adaptive RAG system.

Features:
- PDF document upload and indexing
- Hybrid retrieval with Reciprocal Rank Fusion (RRF)
- Adaptive responses based on user expertise
- Multiple embedding model support (including medical-specialized)

Usage:
    streamlit run app.py
"""

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import streamlit as st
from dotenv import find_dotenv, load_dotenv

# LangChain imports
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma

from eval.adaptive_vs_generic import run_adaptive_vs_generic
from eval.classification_accuracy import run_classification_accuracy
from eval.format_compliance import run_format_compliance
from eval.hybrid_comparison import run_hybrid_comparison
from eval.latency_measurement import run_latency_measurement
from eval.metrics import calculate_all_metrics
from eval.model_comparison import run_model_comparison
from eval.persona_evaluation import run_persona_evaluation
from eval.readability_analysis import run_readability_analysis

# Local imports
from src.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_TOP_K,
    EMBEDDING_MODELS,
    FAITHFULNESS_BLOCK_THRESHOLD,
    HNSW_COLLECTION_METADATA,
    # New LLM provider configs
    LLM_PROVIDERS,
    OLLAMA_MODELS,
    OPENAI_MODELS,
)
from src.embeddings import create_embedder, get_model_info
from src.faithfulness import FAITHFULNESS_WARNING_THRESHOLD, FaithfulnessChecker
from src.ingestion import DocumentIngester
from src.llm import LLMFactory, OllamaProvider
from src.ocr import OCRFactory
from src.personas import UserType, detect_user_type, get_response_config
from src.prompts import SYSTEM_PROMPT, build_adaptive_prompt
from src.query_classifier import classify_query
from src.retrieval import HybridRetriever
from src.utils import (
    calculate_diversity_score,
    calculate_text_hash,
    deduplicate_documents,
)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

load_dotenv(find_dotenv())
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ==============================================================================
# CUSTOM CSS
# ==============================================================================

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&display=swap');

/* Font stack */
html, body, [class*="css"] {
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

/* App shell */
.stApp { background-color: #F1F5F9; }

/* Sidebar — deep navy */
[data-testid="stSidebar"] {
  background-color: #0B1829;
  border-right: none;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] .stCaption p { color: #94A3B8; }
[data-testid="stSidebar"] hr { border-color: rgba(255, 255, 255, 0.1); }
[data-testid="stSidebar"] .stMarkdown p { color: #94A3B8; font-size: 0.875rem; }
[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  margin-bottom: 0.75rem;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  font-weight: 600;
  color: #E2E8F0;
}

/* Primary buttons — navy → teal gradient */
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #0B1829 0%, #0EA5C9 100%);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  letter-spacing: 0.02em;
  padding: 0.5rem 1.25rem;
  transition: opacity 0.15s;
}
.stButton > button[kind="primary"]:hover { opacity: 0.9; }

/* Secondary buttons — teal border */
.stButton > button[kind="secondary"] {
  background-color: #fff;
  color: #0EA5C9;
  border: 1.5px solid #0EA5C9;
  border-radius: 6px;
  font-weight: 600;
  padding: 0.5rem 1.25rem;
}

/* Text input */
.stTextInput input {
  border: 1.5px solid #D0D9E8;
  border-radius: 6px;
  font-size: 0.95rem;
  padding: 0.6rem 0.875rem;
  transition: border-color 0.15s;
}
.stTextInput input:focus {
  border-color: #0EA5C9;
  box-shadow: 0 0 0 3px rgba(14, 165, 201, 0.15);
}

/* Expanders — card style */
[data-testid="stExpander"] {
  border: 1px solid #D0D9E8;
  border-radius: 8px;
  background: #fff;
  margin-bottom: 0.75rem;
}
[data-testid="stExpander"] summary { font-weight: 600; color: #111827; }

/* Metric labels */
[data-testid="metric-container"] {
  background: #fff;
  border: 1px solid #D0D9E8;
  border-radius: 8px;
  padding: 1rem;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
  color: #6B7280;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
  color: #111827;
  font-size: 1.5rem;
  font-weight: 700;
}

/* Tabs — underline style */
.stTabs [data-baseweb="tab-list"] { border-bottom: 2px solid #D0D9E8; gap: 0; }
.stTabs [data-baseweb="tab"] {
  font-weight: 600;
  color: #6B7280;
  padding: 0.625rem 1.25rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
}
.stTabs [aria-selected="true"] { color: #0EA5C9; border-bottom-color: #0EA5C9; }

/* Alert boxes — left-border variant */
[data-testid="stAlert"] { border-radius: 6px; }

/* Section header custom class */
.section-header { margin: 1.5rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid #0EA5C9; }
.section-header h2 { font-size: 1.125rem; font-weight: 700; color: #111827; margin: 0; }
.section-subtitle { font-size: 0.875rem; color: #6B7280; margin: 0.25rem 0 0; }

/* App header */
.app-header {
  background: #0A2F5C;
  color: #fff;
  padding: 1.25rem 1.5rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
}
.app-header__brand { font-size: 1.375rem; font-weight: 700; letter-spacing: -0.01em; }
.app-header__tagline { font-size: 0.875rem; color: #93C5FD; margin-top: 0.25rem; }
.app-header__badges { margin-top: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }

/* Badges */
.badge {
  background: rgba(255,255,255,0.15);
  color: #fff;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.25rem 0.625rem;
  border-radius: 999px;
  letter-spacing: 0.03em;
}

/* Persona level pill */
.persona-pill {
  display: inline-block;
  padding: 0.25rem 0.875rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.persona-novice       { background: #E0F2FE; color: #0369A1; }
.persona-intermediate { background: #D1FAE5; color: #065F46; }
.persona-expert       { background: #EDE9FE; color: #5B21B6; }
.persona-regulatory   { background: #FEF3C7; color: #92400E; }
.persona-executive    { background: #FFE4E6; color: #9F1239; }

/* Response card */
.response-card {
  background: #fff;
  border: 1px solid #D0D9E8;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1rem;
}

/* Source chunk card */
.source-chunk {
  background: #F8FAFC;
  border: 1px solid #D0D9E8;
  border-radius: 6px;
  padding: 1rem;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
  line-height: 1.6;
  color: #374151;
  font-family: 'Courier New', Courier, monospace;
  white-space: pre-wrap;
}
.source-chunk__label {
  font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 0.75rem;
  font-weight: 700;
  color: #6B7280;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 0.5rem;
}

/* Disclaimer */
.ai-disclaimer {
  font-size: 0.75rem;
  color: #9CA3AF;
  border-top: 1px solid #E5EAF0;
  padding-top: 0.625rem;
  margin-top: 0.5rem;
}

/* Footer */
.app-footer {
  text-align: center;
  padding: 1.5rem;
  color: #9CA3AF;
  font-size: 0.8rem;
  border-top: 1px solid #D0D9E8;
  margin-top: 2rem;
}
.app-footer strong { color: #6B7280; }

/* Sidebar section labels */
.sidebar-label {
  font-size: 0.7rem;
  font-weight: 700;
  color: #64748B;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin: 0.5rem 0 0.25rem;
}

/* Sidebar brand block */
.sidebar-brand { padding: 1.25rem 0 0.75rem; margin-bottom: 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.1); }
.sidebar-brand__name { font-size: 1.125rem; font-weight: 700; color: #F1F5F9; letter-spacing: -0.01em; }
.sidebar-brand__tagline { font-size: 0.75rem; color: #7DD3FC; margin-top: 0.125rem; }

/* Card component */
.card {
  background: #fff;
  border: 1px solid #D0D9E8;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.card-title { font-size: 0.9rem; font-weight: 700; color: #111827; margin-bottom: 0.25rem; }
.card-desc { font-size: 0.8rem; color: #6B7280; }

/* Dot status indicators */
.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.dot-green { background: #16A34A; }
.dot-gray  { background: #9CA3AF; }
.dot-amber { background: #D97706; }

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
.stDeployButton { display: none; }
</style>
"""

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def _section_header(title: str, subtitle: str = "") -> None:
    """Render a styled section header with an optional subtitle."""
    sub = f'<p class="section-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="section-header"><h2>{title}</h2>{sub}</div>',
        unsafe_allow_html=True,
    )


def _persona_pill(user_type: UserType) -> str:
    """Return an HTML pill badge for the detected user level."""
    classes = {
        UserType.NOVICE: "persona-novice",
        UserType.INTERMEDIATE: "persona-intermediate",
        UserType.EXPERT: "persona-expert",
        UserType.REGULATORY: "persona-regulatory",
        UserType.EXECUTIVE: "persona-executive",
    }
    return (
        f'<span class="persona-pill {classes.get(user_type, "")}">{user_type.value.title()}</span>'
    )


# ==============================================================================
# STREAMLIT PAGE CONFIG
# ==============================================================================

st.set_page_config(
    page_title="Adaptive RAG Clinical Assistant",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject CSS
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Sidebar brand block
st.sidebar.markdown(
    """
<div class="sidebar-brand">
  <div class="sidebar-brand__name">ClinicalRAG</div>
  <div class="sidebar-brand__tagline">Adaptive Intelligence Platform</div>
</div>
""",
    unsafe_allow_html=True,
)

# ==============================================================================
# HEADER
# ==============================================================================

st.markdown(
    """
<div class="app-header">
  <div class="app-header__brand">Clinical RAG Assistant</div>
  <div class="app-header__tagline">Adaptive document intelligence for clinical trials</div>
  <div class="app-header__badges">
    <span class="badge">Hybrid RRF</span>
    <span class="badge">Adaptive Personas</span>
    <span class="badge">Medical Embeddings</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ==============================================================================
# SESSION STATE INITIALIZATION
# ==============================================================================

if "vectordb" not in st.session_state:
    st.session_state.vectordb = None
if "bm25_retriever" not in st.session_state:
    st.session_state.bm25_retriever = None
if "hybrid_retriever" not in st.session_state:
    st.session_state.hybrid_retriever = None
if "document_loaded" not in st.session_state:
    st.session_state.document_loaded = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "splits" not in st.session_state:
    st.session_state.splits = None
if "query_cache" not in st.session_state:
    st.session_state.query_cache = {}
if "current_embedding_model" not in st.session_state:
    st.session_state.current_embedding_model = None
if "ocr_enabled" not in st.session_state:
    st.session_state.ocr_enabled = True
if "ocr_provider" not in st.session_state:
    st.session_state.ocr_provider = "openai"
if "ocr_openai_model" not in st.session_state:
    st.session_state.ocr_openai_model = "gpt-4o"
if "tmp_pdf_path" not in st.session_state:
    st.session_state.tmp_pdf_path = None
if "eval_results" not in st.session_state:
    st.session_state.eval_results = {}
if "benchmark_results" not in st.session_state:
    st.session_state.benchmark_results = {}

# ==============================================================================
# SIDEBAR - USER PROFILE
# ==============================================================================

st.sidebar.markdown('<p class="sidebar-label">Your Profile</p>', unsafe_allow_html=True)
st.sidebar.markdown("Responses adapt to your expertise level")

user_role = st.sidebar.selectbox(
    "Your Role",
    [
        "Research Coordinator (New)",
        "Clinical Research Coordinator",
        "Study Coordinator",
        "Clinical Trial Manager",
        "Senior Clinical Trial Manager",
        "Principal Investigator",
        "Biostatistician",
        "Data Manager",
        "Regulatory Affairs Specialist",
        "Quality Assurance",
        "Medical Monitor",
        "VP Clinical Development",
        "Executive / Sponsor",
    ],
    help="Select your role for tailored responses",
)

experience_years = st.sidebar.slider(
    "Years of Clinical Trial Experience",
    0,
    20,
    2,
    help="Your experience level affects response complexity",
)

user_profile = {
    "role": user_role,
    "experience_years": experience_years,
}

# Detect and display user type
detected_type = detect_user_type(user_profile)
st.sidebar.markdown(
    f"<b>Detected Level:</b> {_persona_pill(detected_type)}",
    unsafe_allow_html=True,
)

level_descriptions = {
    UserType.NOVICE: "Simple explanations with definitions",
    UserType.INTERMEDIATE: "Balanced technical detail",
    UserType.EXPERT: "Deep technical analysis",
    UserType.REGULATORY: "Compliance-focused responses",
    UserType.EXECUTIVE: "Concise summaries with metrics",
}
st.sidebar.caption(level_descriptions[detected_type])

st.sidebar.markdown("---")

# ==============================================================================
# SIDEBAR - CONFIGURATION
# ==============================================================================

st.sidebar.markdown('<p class="sidebar-label">Configuration</p>', unsafe_allow_html=True)

# LLM Provider
with st.sidebar.expander("LLM Provider", expanded=True):
    llm_provider = st.radio(
        "Select Provider",
        LLM_PROVIDERS,
        index=LLM_PROVIDERS.index(DEFAULT_LLM_PROVIDER),
        help="Cloud (OpenAI) or Local (Ollama) inference",
    )

    use_local_llm = llm_provider == "Ollama (Local)"

    if use_local_llm:
        ollama_model_keys = list(OLLAMA_MODELS.keys())
        llm_model = st.selectbox(
            "Local Model",
            ollama_model_keys,
            index=ollama_model_keys.index(DEFAULT_LOCAL_MODEL)
            if DEFAULT_LOCAL_MODEL in ollama_model_keys
            else 0,
            help="Select local model (requires Ollama running)",
        )

        model_config = OLLAMA_MODELS.get(llm_model, {})
        st.info(f"""
        **{llm_model}**
        {model_config.get("description", "")}
        - VRAM: {model_config.get("vram_required", "N/A")}
        - Context: {model_config.get("context_window", "N/A")} tokens
        """)

        try:
            ollama_provider = OllamaProvider(model=llm_model)
            if ollama_provider.is_available():
                st.success("Ollama connected")
            else:
                st.error(f"Model '{llm_model}' not found. Run: ollama pull {llm_model}")
        except Exception as e:
            st.error(f"Ollama not running: {e}")
            st.info("Start Ollama with: `ollama serve`")
    else:
        openai_model_keys = list(OPENAI_MODELS.keys())
        llm_model = st.selectbox(
            "OpenAI Model",
            openai_model_keys,
            index=openai_model_keys.index(DEFAULT_LLM_MODEL)
            if DEFAULT_LLM_MODEL in openai_model_keys
            else 0,
            help="gpt-4o-mini: Fast & cost-effective, gpt-4o: Best quality",
        )

        model_config = OPENAI_MODELS.get(llm_model, {})
        st.info(f"""
        **{llm_model}**
        {model_config.get("description", "")}
        - Context: {model_config.get("context_window", "N/A")} tokens
        """)

        if not OPENAI_API_KEY:
            st.error("OPENAI_API_KEY not found in .env file")
            st.stop()

    # Nucleus sampling — shared across providers
    st.markdown("**Sampling**")
    enable_top_p = st.checkbox(
        "Use nucleus sampling (top_p)",
        value=False,
        help="When enabled, top_p replaces temperature for token selection. "
        "Recommended range: 0.8–0.95.",
    )
    top_p_value: float | None = None
    if enable_top_p:
        top_p_value = st.slider(
            "top_p",
            min_value=0.1,
            max_value=1.0,
            value=0.9,
            step=0.05,
            help="Nucleus sampling cutoff. Only the smallest token set whose "
            "cumulative probability exceeds top_p is sampled from.",
        )

# Embedding Model
with st.sidebar.expander("Embedding Model", expanded=False):
    model_categories = {
        "General Purpose": [],
        "Medical/Scientific": [],
        "Lightweight": [],
    }

    for key, config in EMBEDDING_MODELS.items():
        if config["type"] == "general":
            model_categories["General Purpose"].append(key)
        elif config["type"] == "medical":
            model_categories["Medical/Scientific"].append(key)
        elif config["type"] == "lightweight":
            model_categories["Lightweight"].append(key)

    all_model_keys = []
    for category in model_categories.values():
        all_model_keys.extend(category)

    embedding_model = st.selectbox(
        "Select Embedding Model",
        all_model_keys,
        index=all_model_keys.index("S-PubMedBert-MS-MARCO")
        if "S-PubMedBert-MS-MARCO" in all_model_keys
        else 0,
        help="Medical models recommended for clinical documents",
    )

    model_info = get_model_info(embedding_model)
    if model_info:
        st.info(f"""
        **{model_info["type"].title()} Model**
        - Dimensions: {model_info["dimensions"]}
        - Max Length: {model_info["max_seq_length"]}

        {model_info["description"]}
        """)

# Chunking
with st.sidebar.expander("Chunking", expanded=False):
    chunk_size = st.slider("Chunk Size", 200, 2000, DEFAULT_CHUNK_SIZE, 100)
    chunk_overlap = st.slider("Chunk Overlap", 50, 500, DEFAULT_CHUNK_OVERLAP, 50)

# Retrieval
with st.sidebar.expander("Retrieval", expanded=False):
    top_k = st.slider("Number of Sources", 1, 10, DEFAULT_TOP_K)
    use_hybrid = st.checkbox(
        "Use Hybrid Search (RRF)",
        value=True,
        help="Combines semantic + BM25 with Reciprocal Rank Fusion",
    )
    enable_score_threshold = st.checkbox(
        "Enable Score Threshold",
        value=False,
        help="Filter out low-quality matches below a minimum RRF score. "
        "RRF scores for top-5 results typically range 0.007–0.016.",
    )
    score_threshold: float | None = None
    if enable_score_threshold:
        score_threshold = st.slider(
            "Minimum RRF Score",
            min_value=0.001,
            max_value=0.020,
            value=0.007,
            step=0.001,
            format="%.3f",
            help="Documents with RRF score below this value are excluded.",
        )
    enable_caching = st.checkbox("Enable Query Caching", value=True)

# OCR
with st.sidebar.expander("OCR Settings", expanded=False):
    st.session_state.ocr_enabled = st.checkbox(
        "Enable OCR (auto-detect image pages)",
        value=st.session_state.ocr_enabled,
        help="Scanned pages are automatically detected and processed with OCR",
    )

    if st.session_state.ocr_enabled:
        _ocr_provider_labels = ["Local — Surya", "OpenAI Vision"]
        _ocr_default_idx = 1 if st.session_state.ocr_provider == "openai" else 0
        _selected_ocr_label = st.radio(
            "OCR Engine",
            _ocr_provider_labels,
            index=_ocr_default_idx,
            help="Surya: fast, private, no API cost. OpenAI Vision: high accuracy, uses API tokens.",
        )
        st.session_state.ocr_provider = "openai" if "OpenAI" in _selected_ocr_label else "surya"

        if st.session_state.ocr_provider == "openai":
            st.session_state.ocr_openai_model = st.selectbox(
                "OpenAI Vision Model",
                ["gpt-4o", "gpt-4o-mini"],
                index=0 if st.session_state.ocr_openai_model == "gpt-4o" else 1,
            )
            st.caption("Uses API tokens per OCR'd page")
        else:
            st.caption("Requires surya-ocr installed locally")

# Display
with st.sidebar.expander("Display", expanded=False):
    show_config = st.checkbox("Show Response Configuration", value=True)
    show_retrieval_stats = st.checkbox("Show Retrieval Statistics", value=True)

# Persist directory (derived from selected embedding model)
persist_dir = f"./chroma_adaptive_{embedding_model.replace('/', '_')}"

st.sidebar.markdown("---")

# ==============================================================================
# SIDEBAR - STATUS
# ==============================================================================

st.sidebar.markdown('<p class="sidebar-label">Status</p>', unsafe_allow_html=True)

llm_label = f"{llm_model} ({'Local' if use_local_llm else 'Cloud'})"
st.sidebar.markdown(
    f'<span class="status-dot dot-green"></span>{llm_label}',
    unsafe_allow_html=True,
)

if st.session_state.document_loaded:
    st.sidebar.markdown(
        '<span class="status-dot dot-green"></span>Document indexed',
        unsafe_allow_html=True,
    )
    if st.session_state.splits:
        st.sidebar.caption(f"{len(st.session_state.splits)} chunks")
    if st.session_state.current_embedding_model:
        st.sidebar.caption(st.session_state.current_embedding_model)
else:
    st.sidebar.markdown(
        '<span class="status-dot dot-amber"></span>No document loaded',
        unsafe_allow_html=True,
    )

if st.session_state.query_cache:
    st.sidebar.markdown(
        f'<span class="status-dot dot-green"></span>{len(st.session_state.query_cache)} cached queries',
        unsafe_allow_html=True,
    )

if st.sidebar.button("Clear All Data", type="secondary"):
    import shutil

    tmp_pdf = st.session_state.get("tmp_pdf_path")
    if tmp_pdf and os.path.exists(tmp_pdf):
        try:
            os.unlink(tmp_pdf)
        except OSError:
            pass

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    for model_key in EMBEDDING_MODELS.keys():
        model_dir = f"./chroma_adaptive_{model_key.replace('/', '_')}"
        if os.path.exists(model_dir):
            try:
                shutil.rmtree(model_dir)
            except OSError:
                pass
    st.sidebar.success("Data cleared!")
    st.rerun()

# ==============================================================================
# MAIN CONTENT - TAB LAYOUT
# ==============================================================================

tab_document, tab_query, tab_history, tab_evaluate = st.tabs(
    ["Document", "Query", "History", "Evaluate"]
)

# ==============================================================================
# TAB 1 — DOCUMENT UPLOAD
# ==============================================================================

with tab_document:
    _section_header("Document Upload", "Upload a clinical trial document to build the index")

    uploaded_file = st.file_uploader(
        "Upload IRC or Protocol Document (PDF)",
        type=["pdf"],
        help="Upload a clinical trial document for indexing",
    )

    if uploaded_file and st.button("Build Index", type="primary"):
        with st.spinner(f"Processing with {embedding_model}..."):
            try:
                if (
                    st.session_state.document_loaded
                    and st.session_state.current_embedding_model
                    and st.session_state.current_embedding_model != embedding_model
                ):
                    st.warning(
                        f"Embedding model changed from {st.session_state.current_embedding_model} to {embedding_model}"
                    )
                    st.session_state.vectordb = None
                    st.session_state.bm25_retriever = None
                    st.session_state.hybrid_retriever = None

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.read())
                    tmp_path = tmp_file.name

                st.session_state.tmp_pdf_path = tmp_path

                ocr_provider = None
                if st.session_state.ocr_enabled:
                    if st.session_state.ocr_provider == "openai":
                        ocr_provider = OCRFactory.create(
                            "openai",
                            model=st.session_state.ocr_openai_model,
                            api_key=OPENAI_API_KEY or "",
                        )
                    else:
                        ocr_provider = OCRFactory.create("surya")

                _ocr_progress_bar = st.progress(0.0, text="Processing pages...")
                _page_stats = {"text_native": 0, "needs_ocr": 0}

                def _on_page_progress(page_idx, total_pages, classification):
                    from src.ingestion import PageClassification

                    if classification == PageClassification.TEXT_NATIVE:
                        _page_stats["text_native"] += 1
                    else:
                        _page_stats["needs_ocr"] += 1
                    fraction = (page_idx + 1) / max(total_pages, 1)
                    _ocr_progress_bar.progress(
                        fraction, text=f"Page {page_idx + 1} / {total_pages}"
                    )

                st.info("Ingesting document (auto-detecting scanned pages)...")
                ingester = DocumentIngester(
                    ocr_provider=ocr_provider,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    progress_callback=_on_page_progress,
                )
                splits = ingester.ingest(Path(tmp_path))
                _ocr_progress_bar.empty()

                if not splits:
                    st.error("No content extracted from PDF")
                    st.stop()

                for split in splits:
                    split.metadata.update(
                        {
                            "doc_name": uploaded_file.name,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                unique_pages = len({s.metadata.get("page") for s in splits})
                ocr_label = (
                    f"{_page_stats['needs_ocr']} OCR'd ({st.session_state.ocr_provider.title()})"
                    if st.session_state.ocr_enabled
                    else "OCR disabled"
                )
                st.success(
                    f"Created {len(splits)} chunks from {unique_pages} pages — "
                    f"{_page_stats['text_native']} text-native, {ocr_label}"
                )

                st.info(f"Loading {embedding_model}...")
                embedder = create_embedder(embedding_model)

                if not embedder:
                    st.error("Failed to create embedder")
                    st.stop()

                st.info("Building vector store...")
                vectordb = Chroma.from_documents(
                    documents=splits,
                    embedding=embedder,
                    persist_directory=persist_dir,
                    collection_metadata=HNSW_COLLECTION_METADATA,
                )

                st.info("Building BM25 index...")
                bm25_retriever = BM25Retriever.from_documents(splits)
                bm25_retriever.k = top_k

                hybrid_retriever = HybridRetriever(
                    vectordb=vectordb,
                    bm25_retriever=bm25_retriever,
                    top_k=top_k,
                    score_threshold=score_threshold,
                )

                st.session_state.vectordb = vectordb
                st.session_state.bm25_retriever = bm25_retriever
                st.session_state.hybrid_retriever = hybrid_retriever
                st.session_state.embedder = embedder
                st.session_state.document_loaded = True
                st.session_state.splits = splits
                st.session_state.query_cache = {}
                st.session_state.current_embedding_model = embedding_model

                st.success("Index built successfully!")

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Pages", unique_pages)
                col2.metric("Chunks", len(splits))
                col3.metric(
                    "Avg Chunk Size", f"{np.mean([len(s.page_content) for s in splits]):.0f}"
                )
                col4.metric("Model", embedding_model[:20] + "...")

            except Exception as e:
                st.error(f"Error: {e}")
                logger.exception("Index building failed")

# ==============================================================================
# TAB 2 — QUERY INTERFACE
# ==============================================================================

with tab_query:
    _section_header("Ask Questions", "Query the indexed document with adaptive responses")

    st.markdown("**Quick Start:**")
    col1, col2, col3 = st.columns(3)

    sample_questions = [
        "What is the imaging schedule?",
        "What are the inclusion criteria?",
        "How is response assessed?",
    ]

    for i, col in enumerate([col1, col2, col3]):
        if col.button(sample_questions[i], key=f"sample_{i}"):
            st.session_state.current_query = sample_questions[i]

    query = st.text_input(
        "Your question:",
        value=st.session_state.get("current_query", ""),
        placeholder="Ask anything about the document...",
    )

    if st.button("Get Answer", type="primary"):
        if not query.strip():
            st.warning("Please enter a question")
        elif not st.session_state.document_loaded:
            st.error("Please upload and index a document first")
        else:
            query_hash = calculate_text_hash(query)

            if enable_caching and query_hash in st.session_state.query_cache:
                st.info("Retrieved from cache")
                cached = st.session_state.query_cache[query_hash]
                response_text = cached["response"]
                response_config = cached["config"]
                source_docs = cached["sources"]
                retrieval_stats = cached.get("stats", {})
                faithfulness_result = cached.get("faithfulness")
            else:
                with st.spinner("Generating adaptive response..."):
                    try:
                        query_type = classify_query(query)
                        response_config = get_response_config(detected_type, query_type.value)

                        if not response_config.include_references:
                            st.caption(
                                "Citations are not shown for this expertise level. "
                                "Verify answers against the source document."
                            )

                        if use_hybrid and st.session_state.hybrid_retriever:
                            retrieval_result = (
                                st.session_state.hybrid_retriever.retrieve_with_metadata(
                                    query, top_k=top_k
                                )
                            )
                            source_docs = retrieval_result["documents"]
                            retrieval_stats = retrieval_result["stats"]
                            retrieval_stats["timing"] = retrieval_result["timing"]
                            retrieval_stats["method"] = "Hybrid (RRF)"
                        else:
                            source_docs = st.session_state.vectordb.similarity_search(
                                query, k=top_k
                            )
                            retrieval_stats = {"method": "Semantic only"}

                        source_docs = deduplicate_documents(source_docs)[:top_k]
                        prompt = build_adaptive_prompt(source_docs, query, response_config)

                        if use_local_llm:
                            llm = LLMFactory.create(
                                {
                                    "provider": "ollama",
                                    "model": llm_model,
                                    "num_ctx": 4096,
                                }
                            )
                        else:
                            llm = LLMFactory.create(
                                {
                                    "provider": "openai",
                                    "model": llm_model,
                                    "api_key": OPENAI_API_KEY,
                                }
                            )
                        response_text = llm.generate(
                            prompt=prompt,
                            system_prompt=SYSTEM_PROMPT,
                            temperature=0,
                            top_p=top_p_value,
                        )

                        if st.session_state.get("embedder") is not None:
                            checker = FaithfulnessChecker(embedder=st.session_state.embedder)
                            faithfulness_result = checker.check(response_text, source_docs)
                        else:
                            faithfulness_result = None

                        if enable_caching:
                            st.session_state.query_cache[query_hash] = {
                                "response": response_text,
                                "config": response_config,
                                "sources": source_docs,
                                "stats": retrieval_stats,
                                "faithfulness": faithfulness_result,
                            }

                    except Exception as e:
                        st.error(f"Error: {e}")
                        logger.exception("Query failed")
                        st.stop()

            # Faithfulness gate — hard block for severely ungrounded responses
            _faith_blocked = (
                faithfulness_result is not None
                and faithfulness_result.score < FAITHFULNESS_BLOCK_THRESHOLD
            )

            # Display response
            st.markdown("**Answer**")
            st.markdown('<div class="response-card">', unsafe_allow_html=True)
            if _faith_blocked:
                st.error(
                    f"Response blocked — faithfulness score {faithfulness_result.score:.2f} "
                    f"is below the safety threshold ({FAITHFULNESS_BLOCK_THRESHOLD}). "
                    "This response could not be grounded in the retrieved document context. "
                    "Please consult the source document directly or rephrase your question."
                )
            else:
                st.markdown(response_text, unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown(
                '<p class="ai-disclaimer">AI-generated response based solely on the uploaded document. '
                "Always verify critical clinical or regulatory information against the original source. "
                "This tool does not provide medical advice.</p>",
                unsafe_allow_html=True,
            )

            # Response configuration
            if show_config:
                with st.expander("Response Configuration"):
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("User Level", response_config.user_type.value.title())
                    col2.metric("Query Type", response_config.query_type.title())
                    col3.metric("Detail Level", response_config.detail_level.title())
                    col4.metric("Max Length", f"~{response_config.max_length} words")

                    st.info(f"""
                    **Adaptation Applied:**
                    - Tables: {"Yes" if response_config.use_tables else "No"}
                    - Color Coding: {"Yes" if response_config.color_coding else "No"}
                    - Key Takeaway: {"Yes" if response_config.include_key_takeaway else "No"}
                    - Executive Summary: {"Yes" if response_config.include_executive_summary else "No"}
                    """)

            # Retrieval stats
            if show_retrieval_stats and retrieval_stats:
                with st.expander("Retrieval Statistics"):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Method", retrieval_stats.get("method", "N/A"))
                    col1.metric(
                        "Sources Retrieved", retrieval_stats.get("final_count", len(source_docs))
                    )

                    if "found_in_both" in retrieval_stats:
                        col2.metric("Found in Both", retrieval_stats["found_in_both"])
                        col2.metric("Semantic Only", retrieval_stats.get("semantic_only", 0))
                        col3.metric("Lexical Only", retrieval_stats.get("lexical_only", 0))

                    if "timing" in retrieval_stats:
                        timing = retrieval_stats["timing"]
                        st.markdown(f"""
                        **Timing:**
                        - Semantic: {timing.get("semantic_ms", "N/A")}ms
                        - Lexical: {timing.get("lexical_ms", "N/A")}ms
                        - Fusion: {timing.get("fusion_ms", "N/A")}ms
                        - **Total: {timing.get("total_ms", "N/A")}ms**
                        """)

                    diversity = calculate_diversity_score(source_docs)
                    st.metric("Diversity Score", f"{diversity:.3f}")
                    if diversity < 0.3:
                        st.warning(
                            "Low retrieval diversity — retrieved chunks are highly similar. "
                            "The response may reflect a narrow slice of the document. "
                            "Consider rephrasing your query or increasing the top-K value."
                        )

                    if faithfulness_result is not None:
                        st.metric(
                            "Faithfulness Score",
                            f"{faithfulness_result.score:.2f}",
                            help="Mean cosine similarity between response sentences and retrieved context chunks (0 = ungrounded, 1 = fully grounded).",
                        )
                        if faithfulness_result.score < FAITHFULNESS_WARNING_THRESHOLD:
                            st.warning(
                                f"Low faithfulness score ({faithfulness_result.score:.2f}) — "
                                "the response may contain statements not well-supported by the "
                                "retrieved context. Verify the answer against the source document."
                            )
                        if faithfulness_result.low_confidence_sentences:
                            with st.expander(
                                f"Low-confidence sentences ({len(faithfulness_result.low_confidence_sentences)})"
                            ):
                                lc_scores = [
                                    faithfulness_result.sentence_scores[i]
                                    for i in faithfulness_result.low_confidence_indices
                                ]
                                for sent, score in zip(
                                    faithfulness_result.low_confidence_sentences,
                                    lc_scores,
                                    strict=False,
                                ):
                                    st.markdown(
                                        f'<span style="color: #d97706;">**[{score:.2f}]** {sent}</span>',
                                        unsafe_allow_html=True,
                                    )

            # Source chunks
            if source_docs:
                with st.expander(f"View Sources ({len(source_docs)} chunks)"):
                    for i, doc in enumerate(source_docs, 1):
                        page = doc.metadata.get("page", "N/A")
                        chunk_id = doc.metadata.get("chunk_id", "N/A")
                        st.markdown(
                            f'<div class="source-chunk__label">Source {i} — Page {page} | Chunk {chunk_id}</div>'
                            f'<div class="source-chunk">{doc.page_content}</div>',
                            unsafe_allow_html=True,
                        )

            # Add to history
            st.session_state.chat_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "question": query,
                    "answer": response_text[:500] + "..."
                    if len(response_text) > 500
                    else response_text,
                    "user_level": response_config.user_type.value,
                    "query_type": response_config.query_type,
                    "num_sources": len(source_docs),
                    "method": retrieval_stats.get("method", "Unknown"),
                    "llm_provider": "Local" if use_local_llm else "Cloud",
                    "llm_model": llm_model,
                }
            )

# ==============================================================================
# TAB 3 — CHAT HISTORY
# ==============================================================================

with tab_history:
    _section_header("History", "Recent queries and responses")

    if st.session_state.chat_history:
        with st.expander(
            f"Last {min(5, len(st.session_state.chat_history))} queries", expanded=True
        ):
            for idx, item in enumerate(reversed(st.session_state.chat_history[-5:]), 1):
                st.markdown(f"**Q{idx}:** {item['question']}")
                st.markdown(f"**A{idx}:** {item['answer'][:250]}...")
                st.caption(
                    f"{item['timestamp'][:19]} | "
                    f"{item['user_level'].title()} | "
                    f"{item['query_type'].title()} | "
                    f"{item['num_sources']} sources | "
                    f"{item['method']} | "
                    f"{item.get('llm_model', 'N/A')[:20]} ({item.get('llm_provider', 'N/A')})"
                )
                st.markdown("---")
    else:
        st.info("No queries yet. Ask a question in the Query tab to get started.")

# ==============================================================================
# TAB 4 — EVALUATE
# ==============================================================================

with tab_evaluate:
    _section_header("Evaluate", "Measure system performance and compare retrieval strategies")

    # --- Eval Suite ---
    st.markdown(
        """
<div class="card">
  <div class="card-title">Adaptive Evaluation Suite</div>
  <div class="card-desc">Measure how this adaptive system compares to generic RAG</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not st.session_state.document_loaded:
        st.info("Build an index first to enable document-dependent evals")

    col_eval1, col_eval2 = st.columns(2)

    with col_eval1:
        run_eval_classify = st.checkbox(
            "Classification Accuracy",
            value=True,
            help="Measures how accurately the 9-type query classifier routes queries. No document needed.",
        )
        run_eval_readability = st.checkbox(
            "Readability Analysis",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Proves NOVICE responses are measurably simpler than EXPERT (Flesch-Kincaid grades).",
        )

    with col_eval2:
        run_eval_compliance = st.checkbox(
            "Format Compliance",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Proves adaptive prompt instructions are followed (numbered steps, tables, key takeaways, etc.).",
        )
        run_eval_adaptive = st.checkbox(
            "Adaptive vs Generic",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Head-to-head: adaptive RAG vs a vanilla RAG baseline on compliance, readability, and length adherence.",
        )

    _any_eval_selected = any(
        [run_eval_classify, run_eval_readability, run_eval_compliance, run_eval_adaptive]
    )

    if st.button("Run Selected Evaluations", type="primary", disabled=not _any_eval_selected):
        os.makedirs("results", exist_ok=True)
        pdf_path = st.session_state.get("tmp_pdf_path")

        with st.spinner("Running evaluation suite..."):
            if run_eval_classify:
                df_classify = run_classification_accuracy(output_dir="results")
                st.session_state.eval_results["classify"] = df_classify

            if run_eval_readability and st.session_state.document_loaded and pdf_path:
                df_readability = run_readability_analysis(
                    document_path=str(pdf_path),
                    embedding_model=embedding_model,
                    output_dir="results",
                )
                st.session_state.eval_results["readability"] = df_readability

            if run_eval_compliance and st.session_state.document_loaded and pdf_path:
                df_compliance = run_format_compliance(
                    document_path=str(pdf_path),
                    embedding_model=embedding_model,
                    output_dir="results",
                )
                st.session_state.eval_results["compliance"] = df_compliance

            if run_eval_adaptive and st.session_state.document_loaded and pdf_path:
                df_adaptive = run_adaptive_vs_generic(
                    document_path=str(pdf_path),
                    embedding_model=embedding_model,
                    output_dir="results",
                )
                st.session_state.eval_results["adaptive"] = df_adaptive

        st.success("Evaluation complete!")

    # Eval results
    if st.session_state.eval_results:
        with st.expander("Evaluation Results", expanded=True):
            if "classify" in st.session_state.eval_results:
                df_cl = st.session_state.eval_results["classify"]
                accuracy = df_cl["is_correct"].mean()
                st.subheader("Query Classification Accuracy")
                st.metric("Classifier Accuracy", f"{accuracy:.1%}")

                per_type_df = (
                    df_cl.groupby("expected_type")["is_correct"]
                    .agg(["mean", "count"])
                    .rename(columns={"mean": "accuracy", "count": "total"})
                    .reset_index()
                )
                per_type_df["accuracy"] = per_type_df["accuracy"].map("{:.1%}".format)
                st.dataframe(per_type_df, use_container_width=True)

                _classify_csv = df_cl.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Classification CSV",
                    _classify_csv,
                    file_name="classification_accuracy_results.csv",
                    mime="text/csv",
                )

            if "readability" in st.session_state.eval_results:
                df_rd = st.session_state.eval_results["readability"]
                st.subheader("Readability Analysis")

                novice_grade = df_rd[df_rd["persona"] == "novice"]["flesch_kincaid_grade"].mean()
                expert_grade = df_rd[df_rd["persona"] == "expert"]["flesch_kincaid_grade"].mean()

                col_r1, col_r2 = st.columns(2)
                col_r1.metric("NOVICE FK Grade", f"{novice_grade:.1f}")
                col_r2.metric("EXPERT FK Grade", f"{expert_grade:.1f}")

                if novice_grade < expert_grade:
                    st.success("NOVICE responses are measurably simpler than EXPERT")
                else:
                    st.warning("No significant readability difference detected")

                pivot = df_rd.pivot_table(
                    index="persona",
                    values=["flesch_reading_ease", "flesch_kincaid_grade", "gunning_fog"],
                    aggfunc="mean",
                ).round(2)
                st.dataframe(pivot, use_container_width=True)

                _rd_csv = df_rd.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Readability CSV",
                    _rd_csv,
                    file_name="readability_analysis_results.csv",
                    mime="text/csv",
                )

            if "compliance" in st.session_state.eval_results:
                df_cp = st.session_state.eval_results["compliance"]
                overall = df_cp["compliance_score"].mean()
                st.subheader("Format Compliance")
                st.metric("Overall Compliance", f"{overall:.1%}")

                per_persona_cp = (
                    df_cp.groupby("persona")["compliance_score"]
                    .mean()
                    .reset_index()
                    .rename(columns={"compliance_score": "avg_compliance"})
                )
                per_persona_cp["avg_compliance"] = per_persona_cp["avg_compliance"].map(
                    "{:.1%}".format
                )
                st.dataframe(per_persona_cp, use_container_width=True)

                per_qtype_cp = (
                    df_cp.groupby("query_type")["compliance_score"]
                    .mean()
                    .reset_index()
                    .rename(columns={"compliance_score": "avg_compliance"})
                )
                per_qtype_cp["avg_compliance"] = per_qtype_cp["avg_compliance"].map("{:.1%}".format)
                st.dataframe(per_qtype_cp, use_container_width=True)

                _cp_csv = df_cp.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Compliance CSV",
                    _cp_csv,
                    file_name="format_compliance_results.csv",
                    mime="text/csv",
                )

            if "adaptive" in st.session_state.eval_results:
                df_av = st.session_state.eval_results["adaptive"]
                win_rate = df_av["adaptive_overall_wins"].mean()
                avg_delta = df_av["compliance_delta"].mean()
                read_fit = df_av["persona_appropriate_readability"].mean()

                st.subheader("Adaptive vs Generic RAG")
                st.metric(
                    "Adaptive Win Rate",
                    f"{win_rate:.1%}",
                    delta=f"{win_rate - 0.5:+.1%} vs chance",
                )

                col_a1, col_a2, col_a3 = st.columns(3)
                col_a1.metric("Avg Compliance Delta", f"{avg_delta:+.3f}")
                col_a2.metric("Readability Fit", f"{read_fit:.1%}")
                col_a3.metric(
                    "Length Adherence Delta",
                    f"{(df_av['adaptive_length_adherence'] - df_av['generic_length_adherence']).mean():+.3f}",
                )

                per_persona_av = (
                    df_av.groupby("persona")["adaptive_overall_wins"]
                    .mean()
                    .reset_index()
                    .rename(columns={"adaptive_overall_wins": "win_rate"})
                )
                per_persona_av["win_rate"] = per_persona_av["win_rate"].map("{:.1%}".format)
                st.dataframe(per_persona_av, use_container_width=True)

                _av_csv = df_av.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download Adaptive vs Generic CSV",
                    _av_csv,
                    file_name="adaptive_vs_generic_results.csv",
                    mime="text/csv",
                )

    st.markdown("---")

    # --- Benchmark Evals ---
    st.markdown(
        """
<div class="card">
  <div class="card-title">Benchmark Evaluations</div>
  <div class="card-desc">Measure retrieval performance, embedding quality, and latency</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if not st.session_state.document_loaded:
        st.info("Build an index first to enable benchmark evals")

    col_b1, col_b2 = st.columns(2)

    with col_b1:
        run_bm_models = st.checkbox(
            "Model Comparison",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Compare all embedding models on retrieval speed and diversity. Long-running: 30-60 minutes.",
        )
        run_bm_hybrid = st.checkbox(
            "Hybrid vs Semantic",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Compare hybrid RRF retrieval against semantic-only on diversity and speed. ~5-10 minutes.",
        )

    with col_b2:
        run_bm_personas = st.checkbox(
            "Persona Evaluation",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Generate responses across all 5 personas for all test queries. Saves persona_responses.json. ~10-15 minutes.",
        )
        run_bm_latency = st.checkbox(
            "Latency Measurement",
            value=False,
            disabled=not st.session_state.document_loaded,
            help="Measure end-to-end retrieval + generation latency over multiple runs. ~3 minutes.",
        )

    if run_bm_latency:
        bm_num_runs = st.slider("Latency Runs (per query)", 1, 10, 3)
    else:
        bm_num_runs = 3

    _any_benchmark_selected = any([run_bm_models, run_bm_hybrid, run_bm_personas, run_bm_latency])

    col_btn1, col_btn2 = st.columns([2, 1])

    with col_btn1:
        if col_btn1.button(
            "Run Benchmark Evaluations",
            type="primary",
            disabled=not (_any_benchmark_selected and st.session_state.document_loaded),
        ):
            os.makedirs("results", exist_ok=True)
            pdf_path = st.session_state.get("tmp_pdf_path")

            with st.spinner("Running benchmark evaluations... (this may take several minutes)"):
                if run_bm_models:
                    df_models = run_model_comparison(
                        document_path=str(pdf_path),
                        output_dir="results",
                    )
                    st.session_state.benchmark_results["models"] = df_models

                if run_bm_hybrid:
                    df_hybrid = run_hybrid_comparison(
                        document_path=str(pdf_path),
                        embedding_model=embedding_model,
                        output_dir="results",
                    )
                    st.session_state.benchmark_results["hybrid"] = df_hybrid

                if run_bm_personas:
                    persona_data = run_persona_evaluation(
                        document_path=str(pdf_path),
                        embedding_model=embedding_model,
                        output_dir="results",
                    )
                    st.session_state.benchmark_results["personas"] = persona_data

                if run_bm_latency:
                    df_latency = run_latency_measurement(
                        document_path=str(pdf_path),
                        embedding_model=embedding_model,
                        num_runs=bm_num_runs,
                        output_dir="results",
                    )
                    st.session_state.benchmark_results["latency"] = df_latency

            st.success("Benchmark evaluation complete!")

    with col_btn2:
        if col_btn2.button(
            "Aggregate Metrics",
            help="Combine all results from results/ into final_metrics_summary.txt",
        ):
            with st.spinner("Aggregating metrics..."):
                all_metrics = calculate_all_metrics(results_dir="results")
                st.session_state.benchmark_results["all_metrics"] = all_metrics
            st.success("Metrics aggregated!")

    # Benchmark results display
    if st.session_state.benchmark_results:
        with st.expander("Benchmark Results", expanded=True):
            if "models" in st.session_state.benchmark_results:
                import pandas as pd

                df_m = st.session_state.benchmark_results["models"]
                st.subheader("Embedding Model Comparison")
                best_speed = df_m.groupby("model")["retrieval_time_ms"].mean().idxmin()
                best_diversity = df_m.groupby("model")["diversity_score"].mean().idxmax()
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Fastest Model", best_speed)
                col_m2.metric("Most Diverse Model", best_diversity)
                summary_m = (
                    df_m.groupby("model")
                    .agg(
                        avg_retrieval_ms=("retrieval_time_ms", "mean"),
                        avg_diversity=("diversity_score", "mean"),
                        model_type=("model_type", "first"),
                    )
                    .round(3)
                    .reset_index()
                )
                st.dataframe(summary_m, use_container_width=True)
                st.download_button(
                    "Download Model CSV",
                    df_m.to_csv(index=False).encode("utf-8"),
                    file_name="model_comparison_results.csv",
                    mime="text/csv",
                )

            if "hybrid" in st.session_state.benchmark_results:
                df_h = st.session_state.benchmark_results["hybrid"]
                st.subheader("Hybrid vs Semantic Retrieval")
                col_h1, col_h2, col_h3 = st.columns(3)
                col_h1.metric("Hybrid Diversity", f"{df_h['hybrid_diversity'].mean():.3f}")
                col_h2.metric("Semantic Diversity", f"{df_h['semantic_diversity'].mean():.3f}")
                col_h3.metric("Improvement", f"{df_h['diversity_improvement'].mean():+.3f}")
                st.dataframe(df_h, use_container_width=True)
                st.download_button(
                    "Download Hybrid CSV",
                    df_h.to_csv(index=False).encode("utf-8"),
                    file_name="hybrid_vs_semantic_comparison.csv",
                    mime="text/csv",
                )

            if "personas" in st.session_state.benchmark_results:
                import pandas as pd

                persona_data = st.session_state.benchmark_results["personas"]
                st.subheader("Persona Evaluation")
                rows_p = []
                for entry in persona_data:
                    for persona, resp in entry["responses"].items():
                        rows_p.append(
                            {
                                "query": entry["query"][:40],
                                "persona": persona,
                                "word_count": resp["word_count"],
                                "gen_time_ms": round(resp["generation_time_ms"]),
                            }
                        )
                df_p = pd.DataFrame(rows_p)
                pivot_p = df_p.pivot_table(
                    index="persona",
                    values=["word_count", "gen_time_ms"],
                    aggfunc="mean",
                ).round(0)
                st.dataframe(pivot_p, use_container_width=True)
                st.caption("Full responses saved to results/persona_responses.json")

            if "latency" in st.session_state.benchmark_results:
                df_lat = st.session_state.benchmark_results["latency"]
                st.subheader("Latency Profile")
                col_l1, col_l2, col_l3 = st.columns(3)
                col_l1.metric("Avg Retrieval", f"{df_lat['retrieval_mean_ms'].mean():.0f} ms")
                col_l2.metric("Avg Generation", f"{df_lat['generation_mean_ms'].mean():.0f} ms")
                col_l3.metric("P95 Total", f"{df_lat['total_mean_ms'].quantile(0.95):.0f} ms")
                st.dataframe(df_lat, use_container_width=True)
                st.download_button(
                    "Download Latency CSV",
                    df_lat.to_csv(index=False).encode("utf-8"),
                    file_name="latency_results.csv",
                    mime="text/csv",
                )

            if "all_metrics" in st.session_state.benchmark_results:
                st.subheader("Aggregated Metrics Summary")
                summary_path = Path("results/final_metrics_summary.txt")
                if summary_path.exists():
                    st.code(summary_path.read_text(encoding="utf-8"), language="text")
                st.download_button(
                    "Download Summary TXT",
                    summary_path.read_bytes() if summary_path.exists() else b"",
                    file_name="final_metrics_summary.txt",
                    mime="text/plain",
                )

# ==============================================================================
# FOOTER
# ==============================================================================

llm_mode_text = "Local LLM (Ollama)" if use_local_llm else "Cloud LLM (OpenAI)"
st.markdown(
    f"""
<div class="app-footer">
  <strong>Clinical RAG Assistant</strong> &nbsp;&bull;&nbsp;
  Reciprocal Rank Fusion &nbsp;&bull;&nbsp; Adaptive Personas &nbsp;&bull;&nbsp; Medical Embeddings
  <br>
  {llm_mode_text} &nbsp;&bull;&nbsp; LangChain &nbsp;&bull;&nbsp; ChromaDB &nbsp;&bull;&nbsp; HuggingFace
</div>
""",
    unsafe_allow_html=True,
)
