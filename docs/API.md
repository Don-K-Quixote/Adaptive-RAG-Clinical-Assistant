# API Documentation

## Module: `src.retrieval`

### Class: `ReciprocalRankFusion`

Implements the RRF algorithm from Cormack et al. (2009).

#### Constructor

```python
ReciprocalRankFusion(k: int = 60)
```

**Parameters:**
- `k`: RRF constant. Higher values reduce rank impact. Default: 60 (standard).

#### Methods

##### `fuse(semantic_results, lexical_results, top_n=5) -> List[RRFResult]`

Fuse results from semantic and lexical retrievers.

**Parameters:**
- `semantic_results`: List of Documents from semantic retriever
- `lexical_results`: List of Documents from lexical retriever  
- `top_n`: Number of results to return

**Returns:**
- List of `RRFResult` objects with document, score, and rank info

---

### Class: `HybridRetriever`

High-level interface for hybrid retrieval with RRF.

#### Constructor

```python
HybridRetriever(vectordb, bm25_retriever, rrf_k=60, top_k=5)
```

#### Methods

##### `retrieve(query, top_k=None, return_scores=False) -> List[Document]`

Retrieve documents using hybrid search with RRF fusion.

##### `retrieve_with_metadata(query, top_k=None) -> Dict`

Retrieve with detailed metadata including timing and statistics.

---

## Module: `src.personas`

### Enum: `UserType`

User expertise levels:
- `NOVICE`: New to clinical trials
- `INTERMEDIATE`: Familiar with basics
- `EXPERT`: Clinical professional
- `REGULATORY`: Compliance focused
- `EXECUTIVE`: Decision maker

### Function: `detect_user_type(user_profile) -> UserType`

Detect user type from profile dictionary.

**Parameters:**
- `user_profile`: Dict with `role` (str) and `experience_years` (int)

---

## Module: `src.query_classifier`

### Enum: `QueryType`

Query categories:
- `DEFINITION`, `PROCEDURE`, `COMPLIANCE`, `COMPARISON`
- `NUMERICAL`, `TIMELINE`, `SAFETY`, `ELIGIBILITY`, `COMPLEX`

### Function: `classify_query(query) -> QueryType`

Classify a query string into a QueryType.

---

## Module: `src.prompts`

### Function: `build_adaptive_prompt(documents, query, config) -> str`

Build persona-aware and query-type-aware prompt.

**Parameters:**
- `documents`: Retrieved Document objects
- `query`: User question
- `config`: ResponseConfig object

---

## Module: `src.embeddings`

### Function: `create_embedder(model_key, device="cpu") -> HuggingFaceEmbeddings`

Create embedding model with fallback handling.

**Supported models:**
- `S-PubMedBert-MS-MARCO` (recommended for clinical)
- `BioSimCSE-BioLinkBERT`
- `BioBERT`
- `all-mpnet-base-v2`
- `all-MiniLM-L6-v2`
