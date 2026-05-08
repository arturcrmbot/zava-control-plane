"""policy_cite MCP tool — return a section + verbatim quote for a clause id.

Given a clause label like '§3.1 Meals — UK per-attendee cap GBP 75', look up
the §3.X section in policy.md and return the relevant snippet plus the page-
title-style citation. Used by the notification-composer skill to embed
verbatim policy text in the breach notification.

Falls back to a semantic search via policy_search if the exact §-tag lookup
misses (e.g., when the classifier emitted an old-style clause string).
"""
from __future__ import annotations
import json
import re

from copilot.tools import ToolResult, define_tool
from opentelemetry import trace
from pydantic import BaseModel, Field

from ._otel import traced_tool
from .policy_search import _ensure_index, search


_SECTION_RE = re.compile(r"§\s*([\d.]+)")


def _section_id(clause: str) -> str | None:
    """Extract '3.1' from '§3.1 Meals — UK per-attendee cap GBP 75'."""
    m = _SECTION_RE.search(clause)
    return m.group(1).rstrip(".") if m else None


@traced_tool("policy.cite")
def cite(clause: str) -> dict:
    """Return {section, quote, source} for a policy clause identifier."""
    span = trace.get_current_span()
    span.set_attribute("wpp.policy.clause", clause)

    section_id = _section_id(clause)
    if section_id:
        # Prefer the index entry whose section label starts with the matched id.
        prefix = f"§{section_id}"
        for chunk in _ensure_index():
            if chunk.section.startswith(prefix):
                span.set_attribute("wpp.policy.section_matched", chunk.section)
                return {
                    "section": chunk.section,
                    "quote": chunk.text,
                    "source": "exact-section-match",
                }

    # Fallback: semantic search over the clause string itself.
    results = search(clause, k=1)
    if results:
        top = results[0]
        span.set_attribute("wpp.policy.section_matched", top["section"])
        return {
            "section": top["section"],
            "quote": top["text"],
            "source": "semantic-fallback",
        }
    raise KeyError(f"no policy section matched clause {clause!r}")


class _PolicyCiteParams(BaseModel):
    clause: str = Field(
        description="Policy clause identifier (e.g. '§3.1 Meals — UK per-attendee cap GBP 75')",
    )


@define_tool(
    name="policy_cite",
    description=(
        "Resolve a policy clause identifier to its §-section label and "
        "verbatim quote from the Zava T&E policy. Use to embed exact "
        "policy wording in breach notifications and audit narratives."
    ),
)
def policy_cite_tool(params: _PolicyCiteParams) -> ToolResult:
    try:
        record = cite(params.clause)
    except KeyError as e:
        return ToolResult(
            text_result_for_llm=f"no policy clause matched: {params.clause}",
            result_type="failure",
            error=str(e),
        )
    return ToolResult(text_result_for_llm=json.dumps(record, ensure_ascii=False))
