# Evaluation Suite Guide

## Overview

The evaluation suite answers the core empirical question: **is adaptive RAG measurably better than generic RAG?**

Four original modules measure *operational* properties (timing, diversity, word counts). Four new modules close the remaining gaps:

| Module | What it proves |
|---|---|
| Classification Accuracy | The 9-type query classifier routes correctly — adaptive routing is grounded |
| Readability Analysis | NOVICE responses are measurably simpler than EXPERT — adaptation changes the text |
| Format Compliance | Adaptive prompt instructions are followed (numbered steps, tables, key takeaways, etc.) |
| Adaptive vs Generic | The full adaptive pipeline beats a vanilla RAG baseline on a composite quality score |

---

## Evaluation Modules

### 1. Classification Accuracy (`eval/classification_accuracy.py`)

**What it proves:** The query classifier reliably labels all 9 query types (DEFINITION, PROCEDURE, COMPLIANCE, COMPARISON, NUMERICAL, TIMELINE, SAFETY, ELIGIBILITY, COMPLEX).

**How it works:** Runs the `classify_query()` function against 45 hand-labeled queries (5 per type). No document, no LLM, no API calls. Runs in under 1 second.

**Key metrics:**
- Overall accuracy (target: ≥ 70%)
- Per-type accuracy and F1
- Average classification confidence
- Top misclassification pairs

**Example output snippet:**
```
Overall Accuracy: 82.2%  (37/45 correct)
Avg Confidence:   0.700

Query Type           Correct    Total    Accuracy     Avg Conf
----------------------------------------------------------------
comparison           5          5        100.0%        0.900
compliance           5          5        100.0%        0.700
definition           3          5        60.0%         0.500
eligibility          5          5        100.0%        0.700
...
```

**Output files:**
- `results/classification_accuracy_results.csv`
- `results/classification_confusion_matrix.csv`
- `results/classification_accuracy_summary.txt`

---

### 2. Readability Analysis (`eval/readability_analysis.py`)

**What it proves:** NOVICE responses have a lower Flesch-Kincaid grade level than EXPERT responses — adaptation measurably changes the text complexity.

**How it works:** Reads `persona_responses.json` (written by `--personas`) to avoid extra LLM calls. Computes 7 readability metrics per response using `textstat`.

**Key metrics:**
- Flesch Reading Ease (higher = simpler)
- Flesch-Kincaid Grade Level
- Gunning Fog Index
- Word count, sentence count, difficult words, average sentence length

**Headline finding:** `novice_fk_grade < expert_fk_grade` → ✅ PASS / ❌ FAIL

**Expected ranges:**

| Persona | FK Grade target |
|---|---|
| Novice | 6 – 9 |
| Intermediate | 10 – 13 |
| Expert | 14 – 18 |
| Regulatory | 14 – 18 |
| Executive | 8 – 12 |

**Output files:**
- `results/readability_analysis_results.csv`
- `results/readability_analysis_summary.txt`

**Dependency:** `conda install -c conda-forge textstat`

---

### 3. Format Compliance (`eval/format_compliance.py`)

**What it proves:** Adaptive prompt instructions are actually obeyed — the LLM produces numbered steps for procedures, markdown tables for comparisons, key takeaways for novices, etc.

**How it works:** Reads `persona_responses.json` (zero extra LLM calls). Applies 16 regex-based rules to each response.

**Compliance score** = `passed_applicable_rules / total_applicable_rules` per response.

**16 format rules:**

| Rule | Condition | What is checked |
|---|---|---|
| `procedure_has_numbered_steps` | query_type = procedure | `^\s*\d+[\.\)]\s+\w` (multiline) |
| `comparison_has_table` | query_type = comparison | `\|.+\|.+\|` |
| `eligibility_has_inclusion` | query_type = eligibility | `inclusion\|include\|eligible` |
| `eligibility_has_exclusion` | query_type = eligibility | `exclusion\|exclude\|ineligible` |
| `numerical_leads_with_number` | query_type = numerical | `^[\w\s]{0,60}?\d+` |
| `timeline_contains_timeframe` | query_type = timeline | `\b\d+\s*(day\|week\|month\|year)s?\b` |
| `safety_contains_severity` | query_type = safety | `\b(grade [1-5]\|mild\|moderate\|severe\|serious)\b` |
| `compliance_cites_regulation` | query_type = compliance | `\b(FDA\|EMA\|ICH\|GCP\|21 CFR)\b` |
| `novice_has_bullet_points` | persona = novice | `^\s*[-•*]\s+\w` (multiline) |
| `novice_has_key_takeaway` | persona = novice | `key takeaway\|📌` |
| `novice_defines_terms` | persona = novice | `\(.{3,60}\)` |
| `executive_has_summary` | persona = executive | `executive summary\|in brief\|key point` |
| `executive_has_recommendation` | persona = executive | `recommend\|next step\|action item\|decision` |
| `expert_uses_technical_terms` | persona = expert | `RECIST\|ICH.GCP\|21 CFR\|SUVmax\|iRECIST\|CTCAE` |
| `regulatory_cites_standard` | persona = regulatory | `FDA\|EMA\|ICH\|GCP\|CFR\|guidance\|compliance\|audit` |
| `intermediate_has_example` | persona = intermediate | `for example\|e.g.\|such as` |

**Output files:**
- `results/format_compliance_results.csv`
- `results/format_compliance_summary.txt`

---

### 4. Adaptive vs Generic (`eval/adaptive_vs_generic.py`)

**What it proves:** The full adaptive pipeline beats a vanilla RAG baseline — the "money shot" comparison.

**How it works:** For each of 25 queries (5 per persona), generates two responses using identical PDF, embedding model, and LLM. Differences:

| Dimension | Adaptive | Generic |
|---|---|---|
| Retrieval | HybridRetriever (RRF) | `similarity_search(k=5)` |
| Prompt | `build_adaptive_prompt()` with persona + query-type routing | Static one-liner prompt |

**Win condition:** Adaptive wins on ≥ 2 of 3 criteria:
1. Higher format compliance score
2. FK grade within `PERSONA_GRADE_TARGETS[persona]`
3. Higher length adherence score

**Expected win rate:** > 60%

**Output files:**
- `results/adaptive_vs_generic_results.csv`
- `results/adaptive_vs_generic_detailed.json` (full response texts)
- `results/adaptive_vs_generic_summary.txt`

---

## CLI Usage

```bash
# Step 1: No document needed — instant (<1 second)
python run_eval.py --classify

# Step 2: Generate persona responses (prerequisite for steps 3 & 4)
python run_eval.py --document irc.pdf --personas

# Steps 3 & 4: Reuse persona_responses.json (zero extra LLM calls)
python run_eval.py --document irc.pdf --readability
python run_eval.py --document irc.pdf --compliance

# Step 5: Independent LLM calls for adaptive + generic responses (25 queries × 2 = 50 calls)
python run_eval.py --document irc.pdf --adaptive-vs-generic

# Run everything at once
python run_eval.py --document irc.pdf --all

# Aggregate all results into final_metrics_summary.txt
python run_eval.py --metrics
```

**All flags:**

| Flag | Description | Needs document |
|---|---|---|
| `--classify` | Query classification accuracy | No |
| `--readability` | Readability analysis per persona | Yes |
| `--compliance` | Format compliance evaluation | Yes |
| `--adaptive-vs-generic` | Head-to-head adaptive vs generic | Yes |
| `--models` | Embedding model comparison | Yes |
| `--hybrid` | Hybrid vs semantic retrieval | Yes |
| `--personas` | Persona evaluation | Yes |
| `--latency` | End-to-end latency | Yes |
| `--all` | All of the above | Yes |
| `--metrics` | Aggregate existing results | No |

---

## App UI Usage

After uploading and indexing a document, scroll down to the **📊 Evaluate** section.

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Evaluate                                                     │
│  Measure how this adaptive system compares to generic RAG        │
│                                                                  │
│  ☑ Classification Accuracy  │  ☐ Format Compliance              │
│    (always enabled)         │    (requires document)            │
│                             │                                    │
│  ☐ Readability Analysis     │  ☐ Adaptive vs Generic            │
│    (requires document)      │    (requires document)            │
│                                                                  │
│  ┌──────────────────────┐                                       │
│  │  ▶ Run Selected Evals│                                       │
│  └──────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────┘
```

1. Select which evaluations to run
2. Click **▶ Run Selected Evals**
3. Results appear in the **📊 Evaluation Results** expander at the bottom
4. Download individual CSVs using the download buttons

---

## Interpreting Results

### Classification Accuracy
- **≥ 80%**: Excellent — routing is reliable
- **70–80%**: Acceptable — check per-type breakdown for weak spots
- **< 70%**: Investigate misclassification pairs in the confusion matrix

### Readability Analysis
- Headline: Novice FK grade should be 6–9, Expert 14–18
- If `novice_fk_grade ≥ expert_fk_grade`: the persona adaptation is not producing different text — check LLM prompt instructions

### Format Compliance
- **≥ 80%**: Strong instruction following
- **50–80%**: Acceptable — check per-rule pass rate to identify weak rules
- **< 50%**: Review prompt templates for the failing rules

### Adaptive vs Generic
- **Win rate ≥ 60%**: Adaptive system is demonstrably better
- **Win rate 50–60%**: Marginal advantage — review per-persona breakdown
- **Win rate < 50%**: Investigate: is the generic prompt baseline too strong?

---

## Running the Full Pipeline

```bash
# Recommended order (optimised for LLM call reuse)
python run_eval.py --classify                              # ~1s
python run_eval.py --document irc.pdf --personas           # ~5 min, saves persona_responses.json
python run_eval.py --document irc.pdf --readability        # <1s (reuses persona_responses.json)
python run_eval.py --document irc.pdf --compliance         # <1s (reuses persona_responses.json)
python run_eval.py --document irc.pdf --adaptive-vs-generic  # ~10 min (50 LLM calls)
python run_eval.py --metrics                               # <1s
```

---

## Output Files Reference

| File | Module | Format |
|---|---|---|
| `classification_accuracy_results.csv` | Classification Accuracy | CSV |
| `classification_confusion_matrix.csv` | Classification Accuracy | CSV (9×9 pivot) |
| `classification_accuracy_summary.txt` | Classification Accuracy | Text |
| `readability_analysis_results.csv` | Readability Analysis | CSV |
| `readability_analysis_summary.txt` | Readability Analysis | Text |
| `format_compliance_results.csv` | Format Compliance | CSV |
| `format_compliance_summary.txt` | Format Compliance | Text |
| `adaptive_vs_generic_results.csv` | Adaptive vs Generic | CSV |
| `adaptive_vs_generic_detailed.json` | Adaptive vs Generic | JSON (full text) |
| `adaptive_vs_generic_summary.txt` | Adaptive vs Generic | Text |
| `model_comparison_results.csv` | Model Comparison | CSV |
| `hybrid_vs_semantic_comparison.csv` | Hybrid Comparison | CSV |
| `latency_results.csv` | Latency Measurement | CSV |
| `persona_responses.json` | Persona Evaluation | JSON |
| `final_metrics_summary.txt` | Metrics (all modules) | Text |
