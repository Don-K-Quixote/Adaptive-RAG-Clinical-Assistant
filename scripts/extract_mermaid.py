"""Extract Mermaid diagrams from project_explainer.html and write to .mmd files."""
import re
from pathlib import Path

docs = Path(__file__).parent.parent / "docs"
html = (docs / "project_explainer.html").read_text(encoding="utf-8")

# Find all mermaid pre blocks
blocks = re.findall(r'<pre class="mermaid">([\s\S]*?)</pre>', html)
print(f"Found {len(blocks)} mermaid blocks")

names = ["diag_dataflow", "diag_sequence"]
for i, (name, content) in enumerate(zip(names, blocks)):
    content = content.strip()
    out = docs / f"{name}.mmd"
    out.write_text(content, encoding="utf-8")
    print(f"  {i+1}. {name}.mmd — first line: {content.splitlines()[0]}")
