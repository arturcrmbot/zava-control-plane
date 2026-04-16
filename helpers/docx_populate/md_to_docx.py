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


def _heading_style(level: int) -> str:
    return f"Heading {level}"


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


def render_md_into_doc(doc: DocxDocument, md: str, bullet_style: str = "List Bullet") -> None:
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue

        hm = _HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))
            text = hm.group(2).strip()
            para = doc.add_paragraph(style=_heading_style(level))
            _add_runs(para, text)
            continue

        bm = _BULLET_RE.match(line)
        if bm:
            para = doc.add_paragraph(style=bullet_style)
            _add_runs(para, bm.group(1).strip())
            continue

        nm = _NUMBERED_RE.match(line)
        if nm:
            para = doc.add_paragraph(style="List Number")
            _add_runs(para, nm.group(1).strip())
            continue

        para = doc.add_paragraph()
        _add_runs(para, line.strip())
