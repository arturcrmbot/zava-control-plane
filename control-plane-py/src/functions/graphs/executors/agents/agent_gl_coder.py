# src/functions/graphs/executors/agents/agent_gl_coder.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    classification = input["classification"]["category"]
    vendor = input["vendor"]
    active_gls = input["active_gls"]
    prompt = (
        f"Category: {classification}\n"
        f"Vendor: {json.dumps(vendor)}\n"
        f"Active GLs: {active_gls}\n\n"
        f"Pick GL per your role."
    )
    return {"gl_decision": await run_agent_skill("gl_coder", prompt)}
