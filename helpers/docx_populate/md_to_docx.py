"""Render a restricted Markdown subset into a python-docx Document.

Subset supported:
  - Headings: # ## ### #### (mapped to Heading 1..4)
  - Paragraphs
  - Bullet lists (- or *)
  - Numbered lists (1. 2. 3.)
  - Inline: **bold**, *italic*, `code`, [text](url)

Tables, images, code blocks are NOT supported (by design).
"""
from __future__ import annotations

import re
from docx.document import Document as DocxDocument


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.*)$")

_INLINE_RE = re.compile(
    r"\*\*(?P<bold>[^*]+)\*\*"
    r"|\*(?P<italic>[^*]+)\*"
    r"|`(?P<code>[^`]+)`"
    r"|\[(?P<linktext>[^\]]+)\]\((?P<linkurl>[^)]+)\)"
)


DEFAULT_STYLE_MAP: dict[str, str] = {
    "h1": "Heading 1",
    "h2": "Heading 2",
    "h3": "Heading 3",
    "h4": "Heading 4",
    "h5": "Heading 4",
    "h6": "Heading 4",
    "bullet": "List Bullet",
    "numbered": "List Number",
}


def _add_runs(para, text: str) -> None:
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            para.add_run(text[pos:m.start()])
        if m.group("bold"):
            r = para.add_run(m.group("bold"))
            r.bold = True
        elif m.group("italic"):
            r = para.add_run(m.group("italic"))
            r.italic = True
        elif m.group("code"):
            r = para.add_run(m.group("code"))
            r.font.name = "Consolas"
        elif m.group("linktext"):
            r = para.add_run(m.group("linktext"))
            r.underline = True
        pos = m.end()
    if pos < len(text):
        para.add_run(text[pos:])


def render_md_into_doc(
    doc: DocxDocument,
    md: str,
    bullet_style: str | None = None,
    style_map: dict[str, str] | None = None,
) -> None:
    """Render `md` into `doc`. `style_map` overrides default style names.

    Keys: h1, h2, h3, h4, h5, h6, bullet, numbered. Unspecified keys fall back
    to DEFAULT_STYLE_MAP. The legacy `bullet_style` kwarg (pre-style-map API)
    is still honoured if `style_map` does not set "bullet".
    """
    sm = {**DEFAULT_STYLE_MAP, **(style_map or {})}
    if bullet_style is not None and (not style_map or "bullet" not in style_map):
        sm["bullet"] = bullet_style

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        hm = _HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))
            level = min(level, 6)
            text = hm.group(2).strip()
            para = doc.add_paragraph(style=sm[f"h{level}"])
            _add_runs(para, text)
            continue

        bm = _BULLET_RE.match(line)
        if bm:
            para = doc.add_paragraph(style=sm["bullet"])
            _add_runs(para, bm.group(1).strip())
            continue

        nm = _NUMBERED_RE.match(line)
        if nm:
            para = doc.add_paragraph(style=sm["numbered"])
            _add_runs(para, nm.group(1).strip())
            continue

        para = doc.add_paragraph()
        _add_runs(para, line.strip())
