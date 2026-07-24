"""agent_rag_classifier — invokes the rag-classifier skill via the GHCP SDK.

Pass *only* the rag-classifier skill directory to `skill_directories` so
multiple loaded skills don't fight over the output schema. Tools are SDK-native
(`@define_tool`), registered via `tools=[...]`, and called autonomously by the
model per the skill's `allowed-tools` frontmatter. No prompt-stuffing.
"""
from __future__ import annotations

from api.server.mcp_tools.claim_get_structured import claim_get_structured_tool
from api.server.mcp_tools.policy_search import policy_search_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "rag-classifier"


async def execute(input: dict) -> dict:
    claim_id = input["claim_id"]
    workflow_id = input.get("workflow_id")
    prompt = (
        f"Classify expense claim `{claim_id}` per your role.\n\n"
        f"Use `claim_get_structured` to load the claim record, then use "
        f"`policy_search` to retrieve the relevant §3 rule chunks for the "
        f"claim's category and market. Return exactly the JSON object specified "
        f"in your skill instructions — no prose, no markdown."
    )
    classification = await run_agent_session(
        prompt=prompt,
        tools=[policy_search_tool, claim_get_structured_tool],
        skill_dir=_SKILL_DIR,
        skill_label="rag-classifier",
        workflow_id=workflow_id,
        instance_id=input.get("instance_id"),
    )
    return {"classification": classification}
