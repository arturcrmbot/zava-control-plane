# src/functions/graphs/executors/agents/agent_invoice_classifier.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    prompt = (
        f"Vendor: {json.dumps(input['vendor'])}\n"
        f"Invoice: {json.dumps(input['invoice'])}\n\n"
        f"Classify per your role."
    )
    return {"classification": await run_agent_skill("invoice_classifier", prompt)}
