"""agent_rag_classifier — invokes the rag_classifier skill via the GHCP SDK.

The session is created with `skill_directories=[skills/]` so the SDK
auto-discovers `rag_classifier.skill.md`, and `tools=[policy_search_tool,
claim_get_structured_tool]` so the model can call them autonomously per the
skill's `allowed-tools` frontmatter. No prompt-stuffing of tool results.
"""
from __future__ import annotations

from api.server.mcp_tools.claim_get_structured import claim_get_structured_tool
from api.server.mcp_tools.policy_search import policy_search_tool

from ._wrapper import run_agent_session


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    prompt = (
        f"Classify expense claim `{claim_id}` per your role.\n\n"
        f"Use `claim.getStructured` to load the claim record, then use "
        f"`policy.search` to retrieve the relevant §3 rule chunks for the "
        f"claim's category and market. Return exactly the JSON object specified "
        f"in your skill instructions — no prose, no markdown."
    )
    classification = await run_agent_session(
        prompt=prompt,
        tools=[policy_search_tool, claim_get_structured_tool],
        skill_label="rag_classifier",
    )
    return {"classification": classification}
