# src/functions/graphs/executors/agents/agent_cost_centre_assigner.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    prompt = (
        f"Agency: {input['agency']}\n"
        f"Vendor: {json.dumps(input['vendor'])}\n\n"
        f"Assign cost centre per your role."
    )
    return {"cost_centre_decision": await run_agent_skill("cost_centre_assigner", prompt)}
