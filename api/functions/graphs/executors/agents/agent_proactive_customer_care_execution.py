from __future__ import annotations

import json

from api.server.mcp_tools.customer_care import (
    customer_care_prepare_credit_tool,
    customer_care_prepare_notification_tool,
)

from ._wrapper import SKILLS_DIR, run_agent_session

_SKILL_DIR = SKILLS_DIR / "proactive-customer-care-execution"


async def execute(input: dict) -> dict:
    result = await run_agent_session(
        prompt=(
            "Prepare the typed customer-care world command from the exact "
            "entitlements and approval below. Call both preparation tools for "
            f"each action and return only JSON.\n{json.dumps(input, default=str)}"
        ),
        tools=[
            customer_care_prepare_notification_tool,
            customer_care_prepare_credit_tool,
        ],
        skill_dir=_SKILL_DIR,
        skill_label="proactive-customer-care-execution",
        workflow_id=input.get("workflow_id"),
    )
    return result
