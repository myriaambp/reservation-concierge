"""Render docs/demo-script.md to docs/demo-script.pdf with a more readable
'video script' layout: alternating speaker blocks, time-stamped sections.
Run from the repo root:  python -m docs.build_demo_script_pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown

DOCS = Path(__file__).resolve().parent
SRC = DOCS / "demo-script.md"
OUT = DOCS / "demo-script.pdf"


_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@300;400;500;600&display=swap');
@page {
  size: Letter;
  margin: 0.6in 0.65in 0.7in 0.65in;
  @bottom-center {
    content: "Tableau · 5-min demo script · IEORE4576 Capstone, Columbia Spring 2026 · page " counter(page);
    font-family: 'Inter', sans-serif;
    font-size: 8pt;
    color: #888;
  }
}
* { box-sizing: border-box; }
body {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 10pt;
  line-height: 1.45;
  color: #1a1a1a;
  margin: 0;
}
h1, h2, h3, h4 {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-weight: 600;
  letter-spacing: -0.012em;
  margin: 0;
}
h1 {
  font-size: 26pt;
  line-height: 1;
  margin-bottom: 4pt;
}
h2 {
  font-size: 14pt;
  margin: 14pt 0 5pt;
  padding-bottom: 3pt;
  border-bottom: 0.6pt solid #e0d8c4;
  color: #1a1a1a;
}
h3 {
  font-size: 11pt;
  margin: 12pt 0 4pt 0;
  color: #2d1810;
  background: #fdf6e6;
  padding: 4pt 8pt;
  border-radius: 3pt;
  border-left: 3pt solid #b89968;
  font-weight: 600;
  letter-spacing: 0.01em;
  page-break-after: avoid;
}
h4 { font-size: 10pt; margin: 6pt 0 3pt; }
p {
  margin: 0 0 4pt;
  page-break-inside: avoid;
}
strong { font-weight: 600; color: #1a1a1a; }
em { font-style: italic; color: #2d1810; }
blockquote {
  margin: 0 0 10pt;
  padding: 8pt 14pt;
  border-left: 3pt solid #b89968;
  background: #fffaf0;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-style: italic;
  font-size: 12pt;
  color: #2d1810;
}
hr {
  border: none;
  border-top: 0.5pt solid #e0d8c4;
  margin: 12pt 0;
}
ul, ol { margin: 0 0 8pt 18pt; padding: 0; }
li { margin-bottom: 2pt; }
ul li { list-style: none; padding-left: 0; }
ul li:before { content: "• "; color: #b89968; }
code {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 9pt;
  background: #f5f1e8;
  padding: 0.5pt 4pt;
  border-radius: 2pt;
}
.brandbar {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1.2pt solid #1a1a1a;
  margin-bottom: 10pt;
  padding-bottom: 4pt;
}
.brandbar .left {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 22pt;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.brandbar .right {
  font-size: 8pt;
  color: #6b6453;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
"""


def main() -> int:
    if not SRC.exists():
        print(f"[error] {SRC} not found")
        return 1
    md_text = SRC.read_text()
    body_html = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "extra", "sane_lists"],
        output_format="html5",
    )

    full_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Tableau — Demo Script</title>
<style>{_CSS}</style></head>
<body>
<div class="brandbar">
  <div class="left">Tableau</div>
  <div class="right">5-min demo · video script</div>
</div>
{body_html}
</body></html>"""

    tmp_html = DOCS / "_demo_script_print.html"
    tmp_html.write_text(full_html)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[error] playwright is not installed")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(tmp_html.as_uri())
        page.wait_for_load_state("networkidle")
        page.pdf(
            path=str(OUT),
            format="Letter",
            print_background=True,
            margin={"top": "0.6in", "right": "0.65in", "bottom": "0.7in", "left": "0.65in"},
        )
        browser.close()

    tmp_html.unlink(missing_ok=True)
    print(f"[ok] wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
