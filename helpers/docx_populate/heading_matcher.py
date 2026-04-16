"""Walk a docx body and locate sections by heading text."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn


HEADING_STYLE_PREFIXES = ("heading", "Heading")


@dataclass(frozen=True)
class SectionBounds:
    heading_index: int
    heading_level: int
    end_index: int  # exclusive


def _is_heading(para, target_level: Optional[int] = None) -> tuple[bool, int]:
    style_name = para.style.name if para.style else ""
    for prefix in HEADING_STYLE_PREFIXES:
        if style_name.lower().startswith(prefix.lower()):
            tail = style_name[len(prefix):].strip()
            try:
                level = int("".join(ch for ch in tail if ch.isdigit())[:2] or "0")
            except ValueError:
                level = 0
            if target_level is not None and level != target_level:
                return (False, level)
            return (True, level)
    return (False, 0)


def find_section(doc: DocxDocument, heading_text: str) -> Optional[SectionBounds]:
    """Locate a section by exact or prefix heading-text match. Returns None if not found."""
    body = doc.element.body
    para_map = {p._element: p for p in doc.paragraphs}

    children = list(body.iterchildren())
    heading_idx = -1
    heading_level = 0
    needle = heading_text.strip().lower()

    for i, el in enumerate(children):
        if el.tag != qn("w:p"):
            continue
        para = para_map.get(el)
        if not para:
            continue
        is_h, lvl = _is_heading(para)
        if not is_h:
            continue
        text = para.text.strip().lower()
        if text == needle or text.startswith(needle):
            heading_idx = i
            heading_level = lvl
            break

    if heading_idx < 0:
        return None

    end_idx = len(children)
    for j in range(heading_idx + 1, len(children)):
        el = children[j]
        if el.tag != qn("w:p"):
            continue
        para = para_map.get(el)
        if not para:
            continue
        is_h, lvl = _is_heading(para)
        if is_h and lvl <= heading_level:
            end_idx = j
            break

    return SectionBounds(heading_index=heading_idx, heading_level=heading_level, end_index=end_idx)
