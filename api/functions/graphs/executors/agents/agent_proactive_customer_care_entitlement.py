from __future__ import annotations

import json

from verticals.telco.mcp_tools.customer_care import customer_care_policy_lookup_tool

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "proactive-customer-care-entitlement"


async def execute(input: dict) -> dict:
    impact = input.get("impact_assessment") or {}
    result = await run_agent_session(
        prompt=(
            "Decide care entitlements for these impacted accounts. Use the policy "
            f"tool once per account and return only the required JSON.\n{json.dumps(impact)}"
        ),
        tools=[customer_care_policy_lookup_tool],
        skill_dir=_SKILL_DIR,
        skill_label="proactive-customer-care-entitlement",
        workflow_id=input.get("workflow_id"),
        instance_id=input.get("instance_id"),
    )
    return result
