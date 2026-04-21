# src/functions/graphs/executors/agents/agent_gl_coder.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    # Deterministic demo-fail injection: short-circuit the LLM and return an
    # inactive GL code so validate_gl_active blocks downstream. Keeps the
    # ``demo-fail`` scenario reproducible without any model variance.
    if input.get("force_gl_fail"):
        return {
            "gl_decision": {
                "gl_account_id": "GL-9999",
                "rationale": "demo-fail injection",
            }
        }
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
