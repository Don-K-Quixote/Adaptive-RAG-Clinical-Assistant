#!/usr/bin/env python3
"""Generate a visually polished SVG block diagram for the architecture section
and embed it directly into project_explainer.html, replacing the Mermaid block.
"""

import re
from pathlib import Path

HTML_FILE = Path(__file__).parent.parent / "docs" / "project_explainer.html"

# ─── Palette ────────────────────────────────────────────────────────────────
NAVY    = "#1A1A2E"
BLUE    = "#4361EE";  BLUE_L    = "#EEF2FF"
PURPLE  = "#7209B7";  PURPLE_L  = "#F3E8FF"
PINK    = "#F72585";  PINK_L    = "#FFF1F2"
MAGENTA = "#B5179E";  MAGENTA_L = "#FDF4FF"
GREEN   = "#10B981";  GREEN_L   = "#ECFDF5"
CYAN    = "#06B6D4";  CYAN_L    = "#E0F7FA"
SLATE   = "#64748B"
WHITE   = "#FFFFFF"
BG      = "#F8FAFC"

W, H = 980, 730   # canvas dimensions


# ─── Low-level SVG helpers ───────────────────────────────────────────────────

def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def _rect(x, y, w, h, rx=10, fill=WHITE, stroke=SLATE, sw=1.5) -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

def _text(x, y, msg, anchor="middle", size=11, weight="normal",
          color=NAVY, italic=False, dy=0) -> str:
    style = "italic" if italic else "normal"
    return (f'<text x="{x}" y="{y}" dy="{dy}" text-anchor="{anchor}" '
            f'font-size="{size}" font-weight="{weight}" '
            f'font-style="{style}" fill="{color}">{_esc(msg)}</text>')

def _path(d, stroke=SLATE, sw=1.5, marker="url(#arr)",
          dash="", fill="none") -> str:
    da = f'stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="{d}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" {da} marker-end="{marker}"/>')

def _line(x1, y1, x2, y2, stroke=SLATE, sw=1.5, marker="url(#arr)") -> str:
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{stroke}" stroke-width="{sw}" marker-end="{marker}"/>')


# ─── Component box ───────────────────────────────────────────────────────────

def _component(x, y, w, h, title, sub1="", sub2="", accent=BLUE) -> str:
    """White card with a coloured left accent bar and up to 3 lines of text."""
    out = []
    # shadow
    out.append(_rect(x+2, y+2, w, h, rx=8, fill="#00000012", stroke="none", sw=0))
    # card body
    out.append(_rect(x, y, w, h, rx=8, fill=WHITE, stroke="#E2E5EA", sw=1))
    # accent strip
    out.append(_rect(x, y, 4, h, rx=2, fill=accent, stroke="none", sw=0))

    # vertical text centering
    lines = [l for l in [title, sub1, sub2] if l]
    n = len(lines)
    cx = x + w // 2 + 2
    base_y = y + h // 2 - (n - 1) * 8
    for i, line in enumerate(lines):
        is_title = (i == 0)
        out.append(_text(cx, base_y + i * 16, line,
                         weight="600" if is_title else "normal",
                         size=11 if is_title else 9,
                         color=NAVY if is_title else SLATE))
    return "\n".join(out)


# ─── Group band (background box + label pill) ────────────────────────────────

def _group(x, y, w, h, label, file_hint, accent, fill) -> str:
    out = []
    # background
    out.append(_rect(x, y, w, h, rx=12, fill=fill, stroke=accent, sw=2))
    # label pill centred at top edge
    pill_w = max(len(label) * 7 + 16, 120)
    px = x + (w - pill_w) // 2
    out.append(_rect(px, y - 12, pill_w, 24, rx=6,
                     fill=accent, stroke="none", sw=0))
    out.append(_text(px + pill_w // 2, y + 6, label,
                     size=10, weight="700", color=WHITE))
    if file_hint:
        out.append(_text(x + w // 2, y + h - 10, file_hint,
                         size=8, color=accent, italic=True))
    return "\n".join(out)


# ─── Inline rotated label (for side-channel arrows) ─────────────────────────

def _rot_label(x, y, msg, color=SLATE) -> str:
    return (f'<text x="{x}" y="{y}" text-anchor="middle" font-size="8" '
            f'fill="{color}" font-style="italic" '
            f'transform="rotate(-90 {x} {y})">{_esc(msg)}</text>')


# ─── Arrow note (small pill label floating along an arrow) ───────────────────

def _note(x, y, msg, color=SLATE) -> str:
    w = len(msg) * 5.5 + 8
    out = [f'<rect x="{x-4}" y="{y-10}" width="{w}" height="14" '
           f'rx="4" fill="white" opacity="0.92"/>']
    out.append(_text(x, y, msg, anchor="start", size=8, color=color, italic=True))
    return "\n".join(out)


# ─── Main SVG builder ────────────────────────────────────────────────────────

def build_svg() -> str:
    out = []

    # ── SVG root ──────────────────────────────────────────────────────────────
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="width:100%;height:auto;display:block;'
        f'font-family:\'Inter\',system-ui,sans-serif">'
    )

    # ── defs: arrow markers + shadow filter ──────────────────────────────────
    out.append("""<defs>
  <marker id="arr"  viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#64748b"/></marker>
  <marker id="arrB" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#4361EE"/></marker>
  <marker id="arrP" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#7209B7"/></marker>
  <marker id="arrK" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#F72585"/></marker>
  <marker id="arrM" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#B5179E"/></marker>
  <marker id="arrG" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#10B981"/></marker>
  <marker id="arrC" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9Z" fill="#06B6D4"/></marker>
  <filter id="sh"><feDropShadow dx="0" dy="2" stdDeviation="3" flood-opacity="0.08"/></filter>
</defs>""")

    # ── canvas background ─────────────────────────────────────────────────────
    out.append(_rect(0, 0, W, H, rx=0, fill=BG, stroke="none", sw=0))

    # ══════════════════════════════════════════════════════════════════════════
    # BAND 1 — STREAMLIT FRONTEND  (y 15 → 125)
    # ══════════════════════════════════════════════════════════════════════════
    B1Y, B1H = 15, 110
    out.append(_group(10, B1Y, 960, B1H,
                      "Streamlit Web Interface",
                      "app.py  ·  ~700 lines",
                      BLUE, BLUE_L))

    # components (y: B1Y+15 → B1Y+B1H-10)
    CY1 = B1Y + 15
    CH1 = B1H - 20       # component height inside band
    out.append(_component(22,  CY1, 188, CH1, "User Profile",
                           "Role + Experience", "Years input", BLUE))
    out.append(_component(228, CY1, 188, CH1, "Document Upload",
                           "PDF Clinical Trial", "IRCs & Protocols", BLUE))
    out.append(_component(434, CY1, 188, CH1, "Query Interface",
                           "Natural Language", "Question Input", BLUE))
    # Chat History — output node, use CYAN accent
    out.append(_component(738, CY1, 210, CH1, "Chat History",
                           "Formatted Answer", "Session Cache", CYAN))
    # tiny OUTPUT badge
    out.append(_rect(745, CY1 - 2, 52, 14, rx=4,
                     fill=CYAN, stroke="none", sw=0))
    out.append(_text(771, CY1 + 8, "OUTPUT", size=7, weight="700",
                     color=WHITE))

    # ══════════════════════════════════════════════════════════════════════════
    # BAND 2L — INTELLIGENCE LAYER  (x 10→450,  y 150→300)
    # BAND 2R — DATA STORAGE        (x 465→970, y 150→300)
    # ══════════════════════════════════════════════════════════════════════════
    B2Y, B2H = 150, 155
    # Intelligence
    out.append(_group(10, B2Y, 440, B2H,
                      "Intelligence Layer",
                      "personas.py  ·  query_classifier.py",
                      PURPLE, PURPLE_L))
    out.append(_component(22,  B2Y+18, 190, 60,
                           "Persona Detector",
                           "detect_user_type()", "5 Levels: Novice→Expert", PURPLE))
    out.append(_component(238, B2Y+18, 190, 60,
                           "Query Classifier",
                           "classify(query)", "9 Types: Definition…", PURPLE))
    # Response Config — centred, smaller, at bottom of band
    out.append(_component(120, B2Y+98, 205, 45,
                           "Response Config",
                           "Tables · Length · Style · Format", "", PURPLE))

    # Storage
    out.append(_group(465, B2Y, 505, B2H,
                       "Data Storage",
                       "Built once on document upload",
                       PINK, PINK_L))
    out.append(_component(477, B2Y+18, 225, 60,
                            "ChromaDB Vector Store",
                            "HuggingFace Embeddings", "Cosine similarity search", PINK))
    out.append(_component(722, B2Y+18, 235, 60,
                            "BM25 In-Memory Index",
                            "rank-bm25 library", "Term-frequency search", PINK))

    # ══════════════════════════════════════════════════════════════════════════
    # BAND 3 — HYBRID RETRIEVAL ENGINE  (y 335→465)
    # ══════════════════════════════════════════════════════════════════════════
    B3Y, B3H = 335, 130
    out.append(_group(10, B3Y, 960, B3H,
                       "Hybrid Retrieval Engine",
                       "src/retrieval.py  ·  ReciprocalRankFusion  ·  HybridRetriever",
                       MAGENTA, MAGENTA_L))
    out.append(_component(22,  B3Y+18, 278, B3H-32,
                            "Semantic Search",
                            "similarity_search(query, k=10)",
                            "Meaning-based vector retrieval", MAGENTA))
    out.append(_component(320, B3Y+18, 278, B3H-32,
                            "Lexical Search (BM25)",
                            "BM25Retriever.invoke(query)",
                            "Exact-term keyword retrieval", MAGENTA))
    out.append(_component(618, B3Y+18, 342, B3H-32,
                            "RRF Fusion  ·  score = Σ 1/(k+rank),  k=60",
                            "Rank-based merge of semantic + lexical",
                            "Returns deduplicated top-5 documents", "#9D174D"))

    # ══════════════════════════════════════════════════════════════════════════
    # BAND 4 — RESPONSE GENERATION  (y 497→600)
    # ══════════════════════════════════════════════════════════════════════════
    B4Y, B4H = 497, 103
    out.append(_group(10, B4Y, 960, B4H,
                       "Response Generation",
                       "src/prompts.py  ·  src/llm/factory.py",
                       GREEN, GREEN_L))
    out.append(_component(22,  B4Y+18, 440, B4H-28,
                            "Adaptive Prompt Builder",
                            "Combines: retrieved docs + user query + ResponseConfig",
                            "Persona-aware instructions + source attribution", GREEN))
    out.append(_component(482, B4Y+18, 468, B4H-28,
                            "LLM Factory",
                            "LLMFactory.create(config)  →  LLMProvider instance",
                            "Strategy pattern: swap OpenAI ↔ Ollama with one line", GREEN))

    # ══════════════════════════════════════════════════════════════════════════
    # BAND 5 — LLM PROVIDERS  (y 635→720)
    # ══════════════════════════════════════════════════════════════════════════
    B5Y, B5H = 635, 85
    out.append(_group(10, B5Y, 960, B5H,
                       "LLM Providers",
                       "",
                       CYAN, CYAN_L))
    out.append(_component(22,  B5Y+15, 440, B5H-22,
                            "OpenAI  (Cloud)",
                            "GPT-4o  ·  GPT-4o-mini",
                            "REST API  ·  OPENAI_API_KEY env var", CYAN))
    out.append(_component(482, B5Y+15, 468, B5H-22,
                            "Ollama  (Local / Air-gapped)",
                            "Llama 3.1 8B  ·  BioMistral 7B  ·  MedGemma 4B",
                            "Fully on-premise — no data leaves the device", "#0284C7"))

    # ══════════════════════════════════════════════════════════════════════════
    # ARROWS
    # ══════════════════════════════════════════════════════════════════════════

    # ── B1 → B2L: User Profile → Persona Detector (straight down) ────────────
    out.append(_path(f"M116,{B1Y+B1H} L116,{B2Y+18}",
                     BLUE, 1.5, "url(#arrB)"))

    # ── B1 → B2L: Query Interface → Query Classifier (arc left) ──────────────
    out.append(_path(f"M528,{B1Y+B1H} C528,{B2Y+5} 333,{B2Y+5} 333,{B2Y+18}",
                     BLUE, 1.5, "url(#arrB)"))

    # ── Within B2L: Persona Det + Query Class → Response Config ──────────────
    pd_cx, qc_cx, rc_cx = 117, 333, 222
    pd_by = B2Y + 18 + 60          # bottom of Persona Det
    qc_by = B2Y + 18 + 60          # bottom of Query Class
    rc_ty = B2Y + 98               # top of Response Config
    elbow = rc_ty - 10
    out.append(_path(f"M{pd_cx},{pd_by} L{pd_cx},{elbow} L{rc_cx},{elbow} L{rc_cx},{rc_ty}",
                     PURPLE, 1.5, "url(#arrP)"))
    out.append(_path(f"M{qc_cx},{qc_by} L{qc_cx},{elbow} L{rc_cx},{elbow}",
                     PURPLE, 1.5, "url(#)"))   # converge (no arrowhead on merge segment)

    # ── B1 → B2R: Document Upload → ChromaDB + BM25 (arcs right) ─────────────
    out.append(_path(
        f"M322,{B1Y+B1H} C322,{B2Y-5} 589,{B2Y-5} 589,{B2Y+18}",
        PINK, 1.5, "url(#arrK)"))
    out.append(_path(
        f"M362,{B1Y+B1H} C362,{B2Y-5} 839,{B2Y-5} 839,{B2Y+18}",
        PINK, 1.5, "url(#arrK)"))
    out.append(_note(368, B2Y - 8, "PyPDFLoader → Splitter → Chunks", PINK))

    # ── B2R → B3: ChromaDB → Semantic Search  (route left through inter-band gap) ─
    # Drop from ChromaDB bottom, curve left into Retrieval
    cdb_cx = 589
    bm25_cx = 839
    ss_cx = 161     # Semantic Search cx
    ls_cx = 459     # Lexical Search cx
    B2_bottom = B2Y + B2H
    B3_top    = B3Y + 18
    mid_y = (B2_bottom + B3_top) // 2  # ~312

    out.append(_path(
        f"M{cdb_cx},{B2_bottom} L{cdb_cx},{mid_y} L{ss_cx},{mid_y} L{ss_cx},{B3_top}",
        PINK, 1.5, "url(#arrK)", dash="5,3"))
    out.append(_path(
        f"M{bm25_cx},{B2_bottom} L{bm25_cx},{mid_y} L{ls_cx},{mid_y} L{ls_cx},{B3_top}",
        PINK, 1.5, "url(#arrK)", dash="5,3"))
    out.append(_note(ss_cx + 4, mid_y - 3, "vector lookup", PINK))
    out.append(_note(ls_cx + 4, mid_y - 3, "term lookup", PINK))

    # ── B1 Query → B3 (through centre gap x≈457 between B2L and B2R) ──────────
    # Query Interface bottom → descend through gap → fan into Semantic + Lexical
    gap_x = 457
    out.append(_path(
        f"M528,{B1Y+B1H} C528,{B2Y+60} {gap_x},{B2Y+60} {gap_x},{mid_y} "
        f"C{gap_x},{B3_top+5} {ss_cx},{B3_top+5} {ss_cx},{B3_top}",
        BLUE, 1.5, "url(#arrB)"))
    out.append(_path(
        f"M528,{B1Y+B1H} C528,{B2Y+70} {gap_x},{B2Y+70} {gap_x},{mid_y} "
        f"C{gap_x},{B3_top+8} {ls_cx},{B3_top+8} {ls_cx},{B3_top}",
        BLUE, 1.5, "url(#arrB)"))
    out.append(_note(gap_x + 3, B2Y + 120, "user query", BLUE))

    # ── Within B3: Semantic + Lexical → RRF Fusion ────────────────────────────
    B3_mid_y = B3Y + 18 + (B3H - 32) // 2   # vertical mid of band-3 boxes
    out.append(_path(f"M300,{B3_mid_y} L618,{B3_mid_y}",
                     MAGENTA, 2, "url(#arrM)"))
    out.append(_path(f"M598,{B3_mid_y} L618,{B3_mid_y}",
                     MAGENTA, 2, "url(#)"))
    out.append(_note(315, B3_mid_y - 4, "ranked candidates", MAGENTA))

    # ── B2L (Response Config) → B4 (Prompt Builder) via left-side channel ─────
    rc_bottom_x = 120       # left edge of Response Config
    rc_bottom_y = B2Y + 98 + 45   # bottom of Response Config
    left_ch = 5             # left-side channel x
    out.append(_path(
        f"M{rc_bottom_x},{rc_bottom_y} L{left_ch},{rc_bottom_y} "
        f"L{left_ch},{B4Y+18} L22,{B4Y+18}",
        PURPLE, 1.5, "url(#arrP)", dash="6,3"))
    out.append(_rot_label(left_ch - 2, (rc_bottom_y + B4Y + 18) // 2,
                           "ResponseConfig", PURPLE))

    # ── B3 (RRF Fusion) → B4 (Prompt Builder) ────────────────────────────────
    rrf_bottom_y = B3Y + B3H
    pb_top_y = B4Y + 18
    out.append(_path(
        f"M789,{rrf_bottom_y} C789,{pb_top_y-15} 462,{pb_top_y-15} 462,{pb_top_y}",
        MAGENTA, 2, "url(#arrM)"))
    out.append(_note(520, (rrf_bottom_y + pb_top_y) // 2 - 3,
                      "top-5 docs + scores + metadata", MAGENTA))

    # ── Within B4: Prompt Builder → LLM Factory ──────────────────────────────
    pb_mid_y = B4Y + 18 + (B4H - 28) // 2
    out.append(_path(f"M462,{pb_mid_y} L482,{pb_mid_y}",
                     GREEN, 2, "url(#arrG)"))
    out.append(_note(467, pb_mid_y - 4, "prompt", GREEN))

    # ── B4 (LLM Factory) → B5 (OpenAI + Ollama) ─────────────────────────────
    lf_bottom_y = B4Y + B4H
    b5_top_y    = B5Y + 15
    # LLM Factory → OpenAI (arc left)
    out.append(_path(
        f"M716,{lf_bottom_y} C716,{b5_top_y-10} 242,{b5_top_y-10} 242,{b5_top_y}",
        CYAN, 1.5, "url(#arrC)"))
    # LLM Factory → Ollama (straight down)
    out.append(_path(f"M716,{lf_bottom_y} L716,{b5_top_y}",
                     CYAN, 1.5, "url(#arrC)"))
    out.append(_note(470, (lf_bottom_y + b5_top_y) // 2 + 2,
                      "LLMProvider instance", CYAN))

    # ── B5 (LLMs) → B1 Chat History  via right-side channel ──────────────────
    right_ch = 975
    ch_target_y = B1Y + B1H // 2   # vertical mid of Chat History card
    b5_mid_y    = B5Y + B5H // 2
    out.append(_path(
        f"M922,{b5_mid_y} L{right_ch},{b5_mid_y} "
        f"L{right_ch},{ch_target_y} L948,{ch_target_y}",
        CYAN, 1.5, "url(#arrC)"))
    out.append(_rot_label(right_ch + 2, (b5_mid_y + ch_target_y) // 2,
                           "LLM response", CYAN))

    # ══════════════════════════════════════════════════════════════════════════
    # LEGEND  (bottom strip)
    # ══════════════════════════════════════════════════════════════════════════
    legend_items = [
        (BLUE,    "Frontend"),
        (PURPLE,  "Intelligence"),
        (PINK,    "Storage"),
        (MAGENTA, "Retrieval"),
        (GREEN,   "Generation"),
        (CYAN,    "LLM Providers"),
    ]
    lx = 22
    ly = H - 14
    for color, label in legend_items:
        out.append(_rect(lx, ly - 9, 12, 12, rx=3,
                         fill=color, stroke="none", sw=0))
        out.append(_text(lx + 16, ly, label, anchor="start",
                         size=9, color=SLATE))
        lx += len(label) * 6 + 44

    out.append("</svg>")
    return "\n".join(out)


# ─── HTML injection ───────────────────────────────────────────────────────────

def inject_svg_into_html(svg: str) -> None:
    html = HTML_FILE.read_text(encoding="utf-8")

    # Match the architecture mermaid container (first one, in section-04)
    # It starts with graph TB
    pattern = (
        r'<div class="mermaid-container">\s*'
        r'<pre class="mermaid">\s*graph TB.*?</pre>\s*'
        r'</div>'
    )
    replacement = (
        '<div class="arch-diagram" '
        'style="margin:20px 0;border-radius:12px;overflow:hidden">\n'
        + svg + "\n</div>"
    )
    new_html, n = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if n == 0:
        raise RuntimeError("Could not find architecture mermaid container in HTML.")

    HTML_FILE.write_text(new_html, encoding="utf-8")
    print(f"Injected {len(svg):,} chars of SVG into {HTML_FILE.name}")


if __name__ == "__main__":
    svg = build_svg()
    inject_svg_into_html(svg)
    print("Done.")
