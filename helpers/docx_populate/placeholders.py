"""Resolve inline placeholders in the master docx.

Placeholders handled:
  1. `<<...>>` markers — replace entire paragraph with authored MD content
  2. `Cut and paste below from Artur's document...` — delete the placeholder paragraph

Mid-paragraph markers: when the marker substring appears inside a paragraph
(not at the start), the surrounding text is preserved and the marker itself
is removed; the rendered replacement paragraphs are then inserted AFTER the
modified paragraph.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from docx import Document
from docx.document import Document as DocxDocument

from helpers.docx_populate.md_to_docx import render_md_into_doc


@dataclass(frozen=True)
class PlaceholderRule:
    match_prefix: str
    resolution: Literal["replace_with", "delete_paragraph"]
    content: Optional[str] = None  # MD content for replace_with


def _clear_marker_from_paragraph(para, marker: str) -> None:
    """Remove `marker` substring from `para` in place, preserving surrounding text.

    Concatenates all run texts, replaces the marker, and rebuilds as a single
    run. Fine-grained per-run formatting on the surrounding text is lost —
    acceptable trade-off for the <<...>> markers in the master.
    """
    combined = "".join(r.text for r in para.runs)
    new_text = combined.replace(marker, "")
    # Normalize any double-spaces introduced by the removal.
    while "  " in new_text:
        new_text = new_text.replace("  ", " ")
    new_text = new_text.strip()

    for r in list(para.runs):
        r._element.getparent().remove(r._element)
    if new_text:
        para.add_run(new_text)


def resolve_inline_placeholder(
    doc: DocxDocument,
    rule: PlaceholderRule,
    style_map: dict[str, str] | None = None,
) -> int:
    """Apply the rule to every matching occurrence in `doc`.

    Returns the number of occurrences resolved (0 if no match). Loops until
    no further matches exist so that duplicated markers are all handled.
    """
    needle = rule.match_prefix.strip()
    count = 0

    while True:
        target_para = None
        for para in doc.paragraphs:
            if needle in para.text:
                target_para = para
                break
        if target_para is None:
            return count

        target_el = target_para._element
        parent = target_el.getparent()
        at_start = target_para.text.strip().startswith(needle)

        if rule.resolution == "delete_paragraph":
            if at_start:
                parent.remove(target_el)
            else:
                _clear_marker_from_paragraph(target_para, needle)
            count += 1
            continue

        assert rule.content is not None, "replace_with requires content"
        # Render into the master doc directly so custom style names (e.g.
        # "heading 20", custom table style) resolve against the master's
        # style definitions.
        #
        # Capture all body children appended during rendering (paragraphs
        # AND tables) via identity-based set difference. python-docx inserts
        # new paragraphs BEFORE the body's sectPr, so slice-by-count would
        # include the (stationary-but-shifted) sectPr instead of the new
        # content.
        body = doc.element.body
        children_before = set(body.iterchildren())
        render_md_into_doc(doc, rule.content, style_map=style_map)
        new_elements = [el for el in body.iterchildren() if el not in children_before]

        # Move new elements from the end of body to the correct insertion
        # point next to the target paragraph.
        if at_start:
            target_index = list(parent).index(target_el)
            for new_el in new_elements:
                body.remove(new_el)
                parent.insert(target_index, new_el)
                target_index += 1
            parent.remove(target_el)
        else:
            _clear_marker_from_paragraph(target_para, needle)
            target_index = list(parent).index(target_el) + 1
            for new_el in new_elements:
                body.remove(new_el)
                parent.insert(target_index, new_el)
                target_index += 1

        count += 1
