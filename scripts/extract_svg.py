"""Extract the inline SVG from project_explainer.html and create a screenshot HTML wrapper."""
import re
from pathlib import Path

docs = Path(__file__).parent.parent / "docs"
html_path = docs / "project_explainer.html"
html = html_path.read_text(encoding="utf-8")

# The arch-diagram div wraps the SVG — match up to the first </svg> then close div
m = re.search(r'<div class="arch-diagram"[^>]*>(\s*<svg[\s\S]*?</svg>\s*)</div>', html)
if not m:
    raise RuntimeError("arch-diagram block not found in HTML")

svg = m.group(1).strip()
print(f"SVG extracted, length: {len(svg)} chars")

# Parse viewBox to get natural dimensions
vb = re.search(r'viewBox=["\']([^"\']+)["\']', svg)
if vb:
    _, _, vw, vh = (float(x) for x in vb.group(1).split())
else:
    vw, vh = 980, 730  # fallback

wrapper = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ background: white; width: {int(vw)}px; height: {int(vh)}px; overflow: hidden; }}
svg {{ display: block; }}
</style>
</head>
<body>
{svg}
</body>
</html>"""

out = docs / "arch_screenshot.html"
out.write_text(wrapper, encoding="utf-8")
print(f"Wrapper written: {out}")
print(f"Canvas: {int(vw)} x {int(vh)}")
