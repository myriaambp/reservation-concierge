"""Render docs/one-pager.md to docs/one-pager.pdf with editorial styling.
Run from the repo root:  python -m docs.build_one_pager_pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown

DOCS = Path(__file__).resolve().parent
SRC = DOCS / "one-pager.md"
OUT = DOCS / "one-pager.pdf"


_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');
@page {
  size: Letter;
  margin: 0.5in 0.6in 0.65in 0.6in;
  @bottom-center {
    content: "Tableau · Reservation Concierge · IEORE4576 Capstone, Columbia Spring 2026 · page " counter(page);
    font-family: 'Inter', sans-serif;
    font-size: 7.5pt;
    color: #888;
  }
}
* { box-sizing: border-box; }
body {
  font-family: 'Inter', -apple-system, sans-serif;
  font-size: 9pt;
  line-height: 1.38;
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
  font-size: 22pt;
  line-height: 1;
  margin-bottom: 2pt;
}
h2 {
  font-size: 13pt;
  margin: 11pt 0 4pt;
  padding-bottom: 2pt;
  border-bottom: 0.5pt solid #e0d8c4;
  color: #1a1a1a;
}
h3 {
  font-size: 10.5pt;
  margin: 8pt 0 3pt;
  color: #2d1810;
}
h4 { font-size: 9.5pt; margin: 6pt 0 3pt; }
p { margin: 0 0 5pt; }
strong { font-weight: 600; }
em { font-style: italic; color: #6b6453; }
blockquote {
  margin: 0 0 8pt;
  padding: 6pt 10pt;
  border-left: 2pt solid #b89968;
  background: #fdf6e6;
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-style: italic;
  font-size: 11pt;
  color: #2d1810;
}
hr {
  border: none;
  border-top: 0.5pt solid #e0d8c4;
  margin: 8pt 0;
}
ul, ol { margin: 0 0 6pt 16pt; padding: 0; }
li { margin-bottom: 2pt; }
code {
  font-family: 'SF Mono', Menlo, monospace;
  font-size: 8pt;
  background: #f5f1e8;
  padding: 0.5pt 3pt;
  border-radius: 2pt;
}
pre {
  background: #f5f1e8;
  padding: 6pt 8pt;
  border-radius: 3pt;
  overflow-x: auto;
  font-size: 8pt;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 4pt 0 8pt;
  font-size: 8.5pt;
  page-break-inside: avoid;
}
th {
  text-align: left;
  font-weight: 600;
  border-bottom: 0.7pt solid #1a1a1a;
  padding: 3pt 5pt;
  background: #fafaf7;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-size: 7.5pt;
  color: #2d1810;
}
td {
  padding: 3pt 5pt;
  border-bottom: 0.3pt solid #efe9d8;
  vertical-align: top;
}
td:last-child, th:last-child { text-align: right; }
.tagline {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 14pt;
  font-style: italic;
  color: #6b6453;
  margin: 4pt 0 16pt;
  display: block;
}
a { color: #2d1810; text-decoration: underline; }
.brandbar {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  border-bottom: 1pt solid #1a1a1a;
  margin-bottom: 8pt;
  padding-bottom: 3pt;
}
.brandbar .left {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-size: 18pt;
  font-weight: 600;
  letter-spacing: -0.02em;
}
.brandbar .right {
  font-size: 7.5pt;
  color: #6b6453;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
"""


def md_to_html(md_text: str) -> str:
    body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "extra", "sane_lists"],
        output_format="html5",
    )
    # Promote the first blockquote into a tagline above the H1.
    return body


def main() -> int:
    if not SRC.exists():
        print(f"[error] {SRC} not found")
        return 1
    md_text = SRC.read_text()
    body_html = md_to_html(md_text)

    full_html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Tableau — One-Pager</title>
<style>{_CSS}</style></head>
<body>
<div class="brandbar">
  <div class="left">Tableau</div>
  <div class="right">Reservation Concierge · One-Pager</div>
</div>
{body_html}
</body></html>"""

    tmp_html = DOCS / "_one_pager_print.html"
    tmp_html.write_text(full_html)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[error] playwright is not installed; run `pip install playwright && playwright install chromium`")
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
            margin={"top": "0.7in", "right": "0.75in", "bottom": "0.85in", "left": "0.75in"},
        )
        browser.close()

    tmp_html.unlink(missing_ok=True)
    print(f"[ok] wrote {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
