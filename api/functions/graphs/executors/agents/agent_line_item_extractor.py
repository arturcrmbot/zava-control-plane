# src/functions/graphs/executors/agents/agent_line_item_extractor.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    extracted = input["extracted"]
    workflow_id = input.get("workflow_id")
    line_items_hint = extracted.get("line_items", [])
    prompt = (
        f"Line items region:\n{json.dumps(line_items_hint)}\n\n"
        f"Return parsed line items per your role."
    )
    result = await run_agent_skill("line_item_extractor", prompt, workflow_id=workflow_id)
    if isinstance(result, dict) and "items" in result:
        extracted["line_items"] = result["items"]
    elif isinstance(result, dict) and "line_items" in result:
        extracted["line_items"] = result["line_items"]
    return {"extracted": extracted}
