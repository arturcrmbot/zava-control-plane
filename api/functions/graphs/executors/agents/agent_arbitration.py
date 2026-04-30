"""agent_arbitration — Phase 6 executor. Recommends a reviewer decision."""
from __future__ import annotations

from api.server.mcp_tools.policy_search import policy_search_tool
from api.server.mcp_tools.precedents_search import precedents_search_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "arbitration"


async def execute(input: dict) -> dict:
    claim_id = input.get("claim_id")
    workflow_id = input.get("workflow_id")
    policy_clause = input.get("policy_clause") or input.get("classify", {}).get("policy_clause")
    tier = input.get("escalation_tier") or (input.get("escalation") or {}).get("tier") or "warning"
    justification = input.get("justification") or {}
    just_text = justification.get("text", "(no justification supplied)")

    prompt = (
        f"Recommend an SSC reviewer decision for expense claim `{claim_id}`.\n\n"
        f"Policy clause: {policy_clause!r}\n"
        f"Escalation tier: {tier}\n"
        f"Claimant justification: {just_text!r}\n\n"
        f"Use `policy_search` to confirm the rule and `precedents_search` to "
        f"find historical analogues. Return the JSON object specified in your "
        f"skill — no prose, no markdown."
    )

    recommendation = await run_agent_session(
        prompt=prompt,
        tools=[precedents_search_tool, policy_search_tool],
        skill_dir=_SKILL_DIR,
        skill_label="arbitration",
        workflow_id=workflow_id,
    )
    return {"arbitration": recommendation}
