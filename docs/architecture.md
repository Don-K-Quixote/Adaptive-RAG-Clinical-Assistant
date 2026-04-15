# System Architecture

## Overview

The Adaptive RAG Clinical Assistant is a Streamlit application that answers questions about clinical trial documents (IRC charters, protocols) by combining **hybrid retrieval** with **persona-based response generation**.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Frontend (app.py)            │
│  ┌──────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ User     │  │  Document   │  │   Query Interface  │  │
│  │ Profile  │  │  Upload     │  │   + Chat History   │  │
│  └────┬─────┘  └──────┬──────┘  └────────┬───────────┘  │
└───────┼───────────────┼──────────────────┼──────────────┘
        │               │                  │
        ▼               ▼                  ▼
┌───────────────┐ ┌──────────────┐ ┌───────────────────────┐
│ Persona       │ │  Indexing    │ │   Query Pipeline       │
│ Detection     │ │  Pipeline    │ │                        │
│ (src/personas)│ │              │ │  classify_query()      │
│               │ │ PyPDFLoader  │ │  ──► QueryType         │
│ UserType:     │ │ RecursiveText│ │                        │
│  NOVICE       │ │ Splitter     │ │  detect_user_type()    │
│  INTERMEDIATE │ │ EmbedModel   │ │  ──► UserType          │
│  EXPERT       │ │ ChromaDB     │ │                        │
│  REGULATORY   │ │ BM25Index    │ │  get_response_config() │
│  EXECUTIVE    │ │              │ │  ──► ResponseConfig    │
└───────────────┘ └──────┬───────┘ └──────────┬────────────┘
                         │                    │
                         ▼                    ▼
              ┌──────────────────┐  ┌─────────────────────┐
              │  Vector Store    │  │  Hybrid Retriever   │
              │  (ChromaDB)      │  │  (src/retrieval.py) │
              └──────────────────┘  │                     │
              ┌──────────────────┐  │  Semantic Search    │
              │  BM25 Index      │  │  +                  │
              │  (rank-bm25)     │  │  BM25 Search        │
              └──────────────────┘  │  ──► RRF Fusion     │
                                    └──────────┬──────────┘
                                               │
                                               ▼
                              ┌────────────────────────────┐
                              │   Prompt Builder           │
                              │   (src/prompts.py)         │
                              │                            │
                              │  build_adaptive_prompt()   │
                              │  ResponseStyler            │
                              └──────────────┬─────────────┘
                                             │
                                             ▼
                              ┌────────────────────────────┐
                              │   LLM Factory              │
                              │   (src/llm/)               │
                              │                            │
                              │  OpenAI Provider  ──► API  │
                              │  Ollama Provider  ──► Local│
                              └────────────────────────────┘
```

---

## Component Details

### 1. Document Indexing Pipeline

```
PDF Upload
    │
    ▼
PyPDFLoader  ──► pages: List[Document]
    │
    ▼
RecursiveCharacterTextSplitter
  chunk_size=800, chunk_overlap=150
    │
    ▼
EmbeddingModel (HuggingFace sentence-transformers)
  ┌─ General:    all-mpnet-base-v2, all-MiniLM-L6-v2
  ├─ Medical:    S-PubMedBert-MS-MARCO (default), BioSimCSE, BioBERT
  └─ Lightweight: bert-tiny-mnli
    │
    ▼
ChromaDB (persisted to ./chroma_adaptive_{model}/)
BM25Retriever (in-memory, from rank-bm25)
```

### 2. Hybrid Retrieval with RRF

```
Query
  ├──► Semantic Search (ChromaDB cosine similarity)  ──► top_k docs
  └──► Lexical Search  (BM25)                        ──► top_k docs
             │
             ▼
   Reciprocal Rank Fusion (RRF)
   score(d) = Σ 1 / (k + rank_i(d))   where k=60

             │
             ▼
   Ranked, deduplicated result set ──► top_k final docs
```

### 3. Adaptive Persona System

| UserType     | Trigger                          | Response Style            |
|--------------|----------------------------------|---------------------------|
| NOVICE       | Role contains "New", exp < 2 yrs | Simple, definitions       |
| INTERMEDIATE | Coordinator roles, 2–5 yrs       | Balanced technical detail |
| EXPERT       | PI, Biostatistician, 5+ yrs      | Deep technical analysis   |
| REGULATORY   | Regulatory Affairs, QA           | Compliance-focused        |
| EXECUTIVE    | VP, Sponsor, Executive           | Concise summaries/metrics |

### 4. Query Classification (9 types)

| QueryType       | Example                                 |
|-----------------|-----------------------------------------|
| ELIGIBILITY     | "What are the inclusion criteria?"      |
| SAFETY          | "What AEs require immediate reporting?" |
| EFFICACY        | "How is response assessed?"             |
| PROCEDURE       | "What is the imaging schedule?"         |
| REGULATORY      | "What ICH guidelines apply?"            |
| STATISTICAL     | "What is the sample size calculation?"  |
| OPERATIONAL     | "How are site visits conducted?"        |
| COMPARATIVE     | "How does this differ from SOC?"        |
| GENERAL         | Catch-all                               |

### 5. LLM Providers (src/llm/)

```
LLMFactory.create(config)
      │
      ├── provider="openai"  ──► OpenAIProvider
      │                              └── openai.ChatCompletion API
      │
      └── provider="ollama"  ──► OllamaProvider
                                     └── HTTP to localhost:11434
```

---

## Data Flow Summary

```
User uploads PDF
      │
      ▼
[Indexing] PDF ──► chunks ──► embeddings ──► ChromaDB + BM25
      │
User asks question
      │
      ▼
[Classification]  query ──► QueryType + UserType ──► ResponseConfig
      │
      ▼
[Retrieval]  HybridRetriever ──► RRF ──► top_k chunks
      │
      ▼
[Generation]  build_adaptive_prompt(chunks, query, config) ──► LLM ──► response
      │
      ▼
Streamlit renders response with retrieval stats
```

---

## Key Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Vector store | ChromaDB | Local, no server needed, easy persistence |
| Retrieval | Hybrid RRF | Better recall than semantic-only for clinical text |
| Embedding default | S-PubMedBert-MS-MARCO | Medical domain outperforms general models |
| LLM | Dual (OpenAI + Ollama) | Flexibility: cloud quality vs. local privacy |
| Frontend | Streamlit | Rapid prototyping, no JS required |
| Persona detection | Rule-based (role + years) | Deterministic, interpretable, no latency |
