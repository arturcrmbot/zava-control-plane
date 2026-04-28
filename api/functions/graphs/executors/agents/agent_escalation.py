"""agent_escalation — invokes the escalation-advisor skill.

Called by Phase 4 in-line (not as a separate phase) only on Amber/Red verdicts.
The skill reads `employee_history` natively to decide progressive-enforcement
tier; the agent executor just builds the prompt and registers the tool.
"""
from __future__ import annotations

from api.server.mcp_tools.employee_history import employee_history_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "escalation-advisor"


async def execute(input: dict) -> dict:
    claim_id = input.get("claim_id")
    employee_id = input.get("employee_id")
    verdict = input.get("verdict")
    category = input.get("category")

    # Skip escalation on Green: there's no breach to enforce against.
    if verdict == "green":
        return {"escalation": None}

    if not employee_id:
        return {"escalation": None, "skip_reason": "missing_employee_id"}

    prompt = (
        f"Recommend a progressive-enforcement tier for expense claim "
        f"`{claim_id}` (verdict={verdict}, category={category}, "
        f"employee={employee_id}). Use `employee_history` to load the "
        f"employee's recent breaches, then return the JSON object specified "
        f"in your skill — no prose."
    )

    recommendation = await run_agent_session(
        prompt=prompt,
        tools=[employee_history_tool],
        skill_dir=_SKILL_DIR,
        skill_label="escalation-advisor",
    )
    return {"escalation": recommendation}
