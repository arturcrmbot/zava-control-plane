"""agent_rag_classifier — pre-fetches claim and policy context in Python, then
invokes the rag_classifier skill via the GHCP wrapper.

The MCP tools (policy.search, claim.getStructured) are pure Python helpers in
this POC, not GHCP-wired tool servers, so the model cannot call them at runtime.
Instead, we resolve the tool calls in process and embed the results in the user
prompt — the model receives the claim JSON and the top-k relevant policy chunks
as context and returns a structured verdict.

For OTEL fidelity the helper calls still emit their own spans, so the trace
still shows policy.search and claim.getStructured side-by-side per claim.
"""
from __future__ import annotations
import json

from api.server.mcp_tools import claim_get_structured, policy_search

from ._wrapper import run_agent_skill

_TOP_K_POLICY_CHUNKS = 15


def _build_query(claim: dict) -> str:
    """Bias retrieval toward §3 rules over §7 examples.

    Including the claim's amount in the query causes §7 example chunks (which
    contain numbers) to score higher than §3 rule chunks (which contain
    threshold tables). The query intentionally omits numbers and uses
    rule-flavoured terminology ("rule", "cap", "threshold")."""
    category = claim.get("category", "")
    market = claim.get("market", "")
    return f"{category} {market} rule cap threshold per-attendee per-night"


def _format_chunks(chunks: list[dict]) -> str:
    out: list[str] = []
    for c in chunks:
        out.append(f"### {c['section']}\n{c['text']}")
    return "\n\n".join(out)


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]

    claim = claim_get_structured.get_structured(claim_id, include_gold=False)
    chunks = policy_search.search(_build_query(claim), k=_TOP_K_POLICY_CHUNKS)

    prompt = (
        f"Classify the following expense claim per your role.\n\n"
        f"## Claim ({claim_id})\n"
        f"```json\n{json.dumps(claim, indent=2, ensure_ascii=False)}\n```\n\n"
        f"## Relevant policy excerpts\n{_format_chunks(chunks)}\n\n"
        f"Return exactly one JSON object matching the schema in your instructions. "
        f"No prose, no markdown — JSON only."
    )

    classification = await run_agent_skill("rag_classifier", prompt)
    return {"classification": classification}
