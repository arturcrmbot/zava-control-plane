"""Render a markdown file to PDF via Python-Markdown + Edge headless.

Usage:
    python _render_md_pdf.py input.md output.pdf
"""
import sys
import subprocess
from pathlib import Path
import markdown

CSS = r"""
@page { size: A4; margin: 18mm 15mm; }
body {
    font-family: 'Segoe UI', 'Calibri', sans-serif;
    font-size: 10pt;
    line-height: 1.45;
    color: #1a1a1a;
    max-width: 100%;
}
h1 { font-size: 20pt; border-bottom: 2px solid #1a5490; padding-bottom: 6px; margin-top: 0; color: #1a5490; }
h2 { font-size: 15pt; border-bottom: 1px solid #bdbdbd; padding-bottom: 4px; margin-top: 24px; color: #1a5490; page-break-after: avoid; }
h3 { font-size: 12pt; margin-top: 18px; color: #333; page-break-after: avoid; }
h4 { font-size: 11pt; margin-top: 14px; color: #555; }
p { margin: 8px 0; }
ul, ol { margin: 8px 0 8px 24px; padding: 0; }
li { margin: 3px 0; }
code {
    font-family: 'Consolas', 'Courier New', monospace;
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 9pt;
}
pre {
    background: #f4f4f4;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 10px;
    overflow-x: auto;
    font-size: 9pt;
    page-break-inside: avoid;
}
pre code { background: transparent; padding: 0; }
blockquote {
    border-left: 3px solid #1a5490;
    margin: 10px 0;
    padding: 4px 12px;
    color: #555;
    background: #f8fafc;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 9pt;
    page-break-inside: auto;
}
table, th, td { border: 1px solid #d0d0d0; }
th, td { padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #e8eef5; font-weight: 600; color: #1a5490; }
tr:nth-child(even) td { background: #fafafa; }
a { color: #1a5490; text-decoration: none; word-break: break-word; }
a:hover { text-decoration: underline; }
hr { border: none; border-top: 1px solid #d0d0d0; margin: 16px 0; }
strong { color: #1a1a1a; }
"""

def md_to_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        output_format="html5",
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{md_path.stem}</title>
<style>{CSS}</style>
</head><body>{body}</body></html>"""


def render_pdf(html_path: Path, pdf_path: Path) -> int:
    edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    file_url = "file:///" + str(html_path).replace("\\", "/")
    args = [
        edge,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        file_url,
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    return result.returncode


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    md_path = Path(sys.argv[1]).resolve()
    pdf_path = Path(sys.argv[2]).resolve()
    html_path = md_path.with_suffix(".rendered.html")
    html_path.write_text(md_to_html(md_path), encoding="utf-8")
    rc = render_pdf(html_path, pdf_path)
    try:
        html_path.unlink()
    except OSError:
        pass
    print(f"{md_path} -> {pdf_path} (exit {rc})")
    return rc


if __name__ == "__main__":
    sys.exit(main())
