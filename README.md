# Adaptive RAG Clinical Assistant

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg)](https://streamlit.io/)
[![LangChain](https://img.shields.io/badge/LangChain-0.1+-orange.svg)](https://langchain.com/)

A Retrieval-Augmented Generation (RAG) system for clinical trial documentation that **adapts response complexity based on user expertise levels**. Built as part of an M.Tech thesis at IIT Jodhpur.

## Key Innovation

Unlike standard RAG systems that provide one-size-fits-all responses, this system implements:

1. **Reciprocal Rank Fusion (RRF)** - Industry-standard hybrid retrieval combining semantic and lexical search
2. **Expertise-Based Persona Adaptation** - Responses automatically adjust to user's knowledge level
3. **Query-Type Detection** - Different formatting for different question types
4. **Medical-Specialized Embeddings** - PubMedBERT, BioLinkBERT for clinical documents
5. **Dual LLM Provider Support** - Cloud (OpenAI GPT-4o) and Local (Ollama) via unified factory

## Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Technical Details](#-technical-details)
- [Evaluation Results](#-evaluation-results)
- [Contributing](#-contributing)
- [License](#-license)
- [Citation](#-citation)

## Features

### Hybrid Retrieval with RRF

Combines semantic search (dense embeddings) with BM25 lexical search using **Reciprocal Rank Fusion**:

```
RRF Score(d) = Σ 1/(k + rank_i(d))
```

This approach is used by Elasticsearch, Azure Cognitive Search, and Pinecone because it:
- Handles score scale differences naturally
- Requires no score normalization
- Emphasizes documents ranked highly by multiple retrievers

### Adaptive Personas (5 Expertise Levels)

| Persona | Adaptation Strategy |
|---------|---------------------|
| **Novice** | Simple language, term definitions, bullet points, key takeaways |
| **Intermediate** | Standard terminology, practical examples, balanced depth |
| **Expert** | Technical precision, edge cases, regulatory citations |
| **Regulatory** | Compliance focus, audit considerations, formal language |
| **Executive** | Executive summary, metrics, recommendations, concise |

### Query Type Classification (9 Categories)

| Type | Example | Format |
|------|---------|--------|
| Definition | "What is RECIST?" | Clear definition → expanded context |
| Procedure | "How to measure lesions?" | Numbered steps with considerations |
| Compliance | "FDA requirements for..." | Regulatory citations, audit notes |
| Comparison | "Difference between CR and PR?" | Comparison table |
| Numerical | "How many target lesions?" | Number first, then context |
| Timeline | "When is baseline imaging?" | Chronological presentation |
| Safety | "Adverse events for contrast?" | Severity classification |
| Eligibility | "Inclusion criteria?" | Checklist format |
| Complex | Multi-part questions | Systematic breakdown |

### Medical Embedding Models

| Model | Type | Best For |
|-------|------|----------|
| S-PubMedBert-MS-MARCO | Medical | Clinical trials, IRC documents |
| BioSimCSE-BioLinkBERT | Medical | Biomedical literature |
| BioBERT | Medical | PubMed abstracts |
| all-mpnet-base-v2 | General | Mixed content |
| all-MiniLM-L6-v2 | General | Fast prototyping |
| bert-tiny-mnli | General | Ultra-fast lightweight inference |

### Dual LLM Provider Support

| Provider | Models | Use Case |
|----------|--------|----------|
| **OpenAI (Cloud)** | GPT-4o, GPT-4o-mini | High accuracy, cloud deployment |
| **Ollama (Local)** | llama3.1:8b, biomistral-7b, gemma2:9b, medgemma:4b | HIPAA-compliant local deployment |

Both providers are accessed via a unified `LLMFactory` abstraction layer, enabling seamless switching.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                           │
│                    (Streamlit Web App)                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    User Profile Detection                        │
│              ┌──────────────────────────────┐                   │
│              │  Role + Experience → Persona │                   │
│              │  (Novice/Expert/Regulatory)  │                   │
│              └──────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Query Classification                          │
│              ┌──────────────────────────────┐                   │
│              │  Pattern Matching → QueryType│                   │
│              │  (Definition/Procedure/etc.) │                   │
│              └──────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Hybrid Retrieval (RRF)                        │
│  ┌─────────────────┐              ┌─────────────────┐           │
│  │ Semantic Search │              │   BM25 Search   │           │
│  │  (ChromaDB +    │              │   (Lexical)     │           │
│  │  Medical Embed) │              │                 │           │
│  └────────┬────────┘              └────────┬────────┘           │
│           │                                │                     │
│           └───────────┬───────────────────┘                     │
│                       ▼                                          │
│           ┌───────────────────────┐                             │
│           │ Reciprocal Rank Fusion│                             │
│           │   score = Σ 1/(k+rank)│                             │
│           └───────────────────────┘                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Adaptive Prompt Generation                      │
│              ┌──────────────────────────────┐                   │
│              │ Persona + QueryType → Prompt │                   │
│              │ (Format, Depth, Style)       │                   │
│              └──────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              LLM Response Generation (Unified Factory)           │
│  ┌──────────────────────┐       ┌──────────────────────┐        │
│  │  Cloud: OpenAI       │       │  Local: Ollama       │        │
│  │  GPT-4o / GPT-4o-mini│       │  llama3.1 / gemma2   │        │
│  │                      │       │  biomistral / medgemma│        │
│  └──────────────────────┘       └──────────────────────┘        │
│              └──────────┬───────────────┘                        │
│                         ▼                                        │
│                ┌──────────────────┐                              │
│                │   LLM Factory    │                              │
│                │ (Provider Agnostic)│                             │
│                └──────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.9+
- **Option A (Cloud):** OpenAI API key
- **Option B (Local):** [Ollama](https://ollama.com/) installed with desired models (e.g., `ollama pull llama3.1:8b`)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Don-K-Quixote/Adaptive-RAG-Clinical-Assistant.git
   cd Adaptive-RAG-Clinical-Assistant
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings:
   #   OPENAI_API_KEY=your-api-key-here    (for cloud mode)
   #   LLM_PROVIDER=ollama                 (for local mode)
   #   OLLAMA_MODEL=llama3.1:8b            (optional, default model)
   ```

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

6. **(Optional) Run evaluation suite**
   ```bash
   python run_eval.py
   ```

## Usage

### Web Interface

1. Open `http://localhost:8501` in your browser
2. Select your role and experience level in the sidebar
3. Upload a clinical trial document (PDF)
4. Click "Build Index" to process the document
5. Ask questions and receive expertise-adapted responses

### Programmatic Usage

```python
from src.retrieval import HybridRetriever, ReciprocalRankFusion
from src.personas import detect_user_type, get_response_config
from src.query_classifier import classify_query
from src.prompts import build_adaptive_prompt

# Setup retrieval
hybrid_retriever = HybridRetriever(vectordb, bm25_retriever)

# Detect user persona
user_profile = {"role": "Clinical Research Coordinator", "experience_years": 2}
user_type = detect_user_type(user_profile)  # → INTERMEDIATE

# Classify query
query = "What is the definition of partial response?"
query_type = classify_query(query)  # → DEFINITION

# Retrieve with RRF
documents = hybrid_retriever.retrieve(query, top_k=5)

# Generate adaptive prompt
config = get_response_config(user_type, query_type.value)
prompt = build_adaptive_prompt(documents, query, config)
```

## Project Structure

```
Adaptive-RAG-Clinical-Assistant/
├── app.py                      # Main Streamlit application
├── run_eval.py                 # Evaluation runner script
├── requirements.txt            # Python dependencies
├── LICENSE                     # Apache 2.0 license
├── .gitignore                  # Git ignore rules
├── .env.example                # Environment variable template
├── .env                        # Environment variables (not tracked)
│
├── src/                        # Source code modules
│   ├── __init__.py             # Package init (version: 2.0.0)
│   ├── config.py               # Configuration constants
│   ├── personas.py             # User type detection & response config
│   ├── query_classifier.py     # Query type classification
│   ├── retrieval.py            # RRF and hybrid retrieval
│   ├── embeddings.py           # Embedding model management
│   ├── prompts.py              # Adaptive prompt generation
│   ├── utils.py                # Utility functions
│   └── llm/                    # LLM provider abstraction layer
│       ├── __init__.py
│       ├── base.py             # Abstract base class for LLM providers
│       ├── factory.py          # LLMFactory: unified provider creation
│       ├── openai_provider.py  # OpenAI GPT-4o/GPT-4o-mini provider
│       └── ollama_provider.py  # Ollama local model provider
│
├── eval/                       # Evaluation scripts
│   ├── __init__.py             # Package init
│   ├── model_comparison.py     # Embedding model benchmarks
│   ├── hybrid_comparison.py    # Hybrid vs semantic comparison
│   ├── latency_measurement.py  # End-to-end latency profiling
│   ├── persona_evaluation.py   # Persona response analysis
│   ├── classification_accuracy.py  # Query classifier accuracy (no doc/LLM)
│   ├── readability_analysis.py     # Per-persona readability metrics
│   ├── format_compliance.py        # Format instruction compliance
│   ├── adaptive_vs_generic.py      # Head-to-head vs plain RAG
│   └── metrics.py              # Aggregate all results
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_config.py          # Configuration tests
│   ├── test_llm_factory.py     # LLM factory tests
│   ├── test_personas.py        # Persona detection tests
│   ├── test_query_classifier.py # Query classifier tests
│   └── test_rrf.py             # RRF algorithm tests
│
├── results/                    # Evaluation results
│   ├── model_comparison_results.csv
│   ├── hybrid_vs_semantic_comparison.csv
│   ├── latency_results.csv
│   ├── final_metrics_summary.txt
│   ├── persona_responses.json
│   └── figures/                # Generated evaluation plots
│       ├── Figure_5.1_Retrieval_Performance.png
│       ├── Figure_5.2_Response_Quality_By_Persona.png
│       └── Figure_5.3_Latency_Analysis.png
│
├── docs/                       # Documentation & thesis materials
│   ├── eval-guide.md           # Full evaluation suite reference
│   └── thesis/
│       └── figures/            # Architecture & design diagrams
│           ├── Figure_3_1_System_Architecture.png
│           └── Figure_4_1_Prompt_Construction.png
│
├── notebooks/                  # Jupyter notebooks (experimental)
│   └── README.md
│
└── .github/
    └── workflows/              # CI/CD (placeholder)
```

## Technical Details

### Reciprocal Rank Fusion (RRF)

Implementation follows Cormack et al. (2009):

```python
def fuse(semantic_results, lexical_results, k=60, top_n=5):
    doc_scores = {}
    
    # Score from semantic retriever
    for rank, doc in enumerate(semantic_results, start=1):
        doc_scores[doc_id] = 1.0 / (k + rank)
    
    # Add score from lexical retriever
    for rank, doc in enumerate(lexical_results, start=1):
        doc_scores[doc_id] += 1.0 / (k + rank)  # Key: scores are SUMMED
    
    # Return top-n by combined RRF score
    return sorted(doc_scores, key=lambda x: x.score, reverse=True)[:top_n]
```

**Why RRF over Weighted Score Fusion?**
- BM25 produces unbounded scores (5.2, 12.7, 23.1...)
- Cosine similarity is bounded [0, 1]
- Direct combination `0.6*semantic + 0.4*bm25` is mathematically problematic
- RRF uses only rank positions, avoiding scale issues entirely

### Persona Detection Logic

```python
def detect_user_type(user_profile):
    role = user_profile.get("role", "").lower()
    experience = user_profile.get("experience_years", 0)
    
    # Priority 1: Role keywords
    if "regulatory" in role or "compliance" in role:
        return REGULATORY
    if "director" in role or "executive" in role:
        return EXECUTIVE
    if "senior" in role or "principal" in role:
        return EXPERT
    
    # Priority 2: Experience-based
    if experience == 0:
        return NOVICE
    elif experience < 3:
        return INTERMEDIATE
    else:
        return EXPERT
```

## Evaluation Suite

The system includes an 8-module evaluation suite that provides a reproducible, empirical case for the system's value over generic RAG.

### CLI quick-start

| Flag | What it measures | Needs document |
|---|---|---|
| `--classify` | Query classifier accuracy across all 9 types | No |
| `--readability`, `--compliance` | Per-persona readability + format instruction following | Yes |
| `--adaptive-vs-generic` | Head-to-head win rate vs vanilla RAG baseline | Yes |

```bash
python run_eval.py --classify
python run_eval.py --document irc.pdf --readability --compliance
python run_eval.py --document irc.pdf --adaptive-vs-generic
python run_eval.py --document irc.pdf --all
python run_eval.py --metrics
```

### App UI

After uploading a document, scroll to the **📊 Evaluate** section in the app. Select the evaluations you want, click **▶ Run Selected Evals**, and download the results as CSV.

See [docs/eval-guide.md](docs/eval-guide.md) for the full reference: metric descriptions, expected ranges, and interpretation guidance.

## Evaluation Results

> **Note:** The results below cover the original 4 operational modules.
> Results for the 4 new modules (Classification Accuracy, Readability Analysis,
> Format Compliance, Adaptive vs Generic) are described in [docs/eval-guide.md](docs/eval-guide.md).

### Retrieval Performance (Hybrid vs Semantic-Only)

| Method | Avg Time (ms) | Diversity Score | Improvement |
|--------|---------------|-----------------|-------------|
| Semantic Only | 29.52 | 0.842 | — |
| **Hybrid (RRF)** | **28.81** | **0.883** | **+4.9% diversity** |

Hybrid retrieval shows **4.9% improvement in diversity** with 80% of queries showing improvement. The hybrid approach also achieves marginally faster retrieval on average.

### Embedding Model Comparison

| Model | Type | Avg Retrieval (ms) | Diversity |
|-------|------|-------------------|-----------|
| bert-tiny-mnli | General | **5.81** | 0.904 |
| BioBERT | Medical | 27.00 | **0.927** |
| all-MiniLM-L6-v2 | General | 111.08 | 0.856 |
| BioSimCSE-BioLinkBERT | Medical | 248.85 | 0.896 |
| S-PubMedBert-MS-MARCO | Medical | 251.27 | 0.854 |

**Recommendation**: S-PubMedBert-MS-MARCO for clinical documents (best balance of medical specificity and retrieval quality). BioBERT offers excellent diversity with fast retrieval.

### End-to-End Latency Profile

| Component | Avg (ms) | P50 (ms) | P95 (ms) |
|-----------|----------|----------|----------|
| Retrieval | 81.57 | — | — |
| LLM Generation | 13,924.91 | — | — |
| **Total** | **14,006.48** | **13,489.44** | **16,708.35** |

Generation dominates total latency (~99.4%). Retrieval overhead is negligible at ~82ms.

### Persona Response Characteristics

| Persona | Avg Words | Avg Generation Time (ms) |
|---------|-----------|--------------------------|
| Novice | 266 | 7,637 |
| Intermediate | 461 | 13,351 |
| Expert | 811 | 23,489 |
| Regulatory | 719 | 18,119 |
| Executive | 282 | 8,129 |

Response length and generation time scale with expected persona complexity, confirming effective adaptation.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this work in your research, please cite:

```bibtex
@thesis{siddiqui2025adaptive,
  title={Adaptive RAG-Based Clinical Assistant with Expertise-Based Response Generation},
  author={Siddiqui, Khalid},
  year={2025},
  school={Indian Institute of Technology Jodhpur},
  type={M.Tech Thesis}
}
```

## Acknowledgments

- **Supervisor**: Dr. Divya Saxena, IIT Jodhpur
- **Frameworks**: LangChain, Streamlit, HuggingFace Transformers, Ollama
- **References**: 
  - Cormack, G. V., Clarke, C. L., & Buettcher, S. (2009). Reciprocal rank fusion outperforms condorcet and individual rank learning methods. SIGIR '09.
  - Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.

---
