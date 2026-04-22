# src/functions/graphs/executors/agents/agent_root_cause_explainer.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    classification = input["exception_classification"]
    prompt = (
        f"Item: {json.dumps(item)}\n"
        f"Classification: {json.dumps(classification)}\n\n"
        f"Explain root cause per your role."
    )
    return {"root_cause": await run_agent_skill("root_cause_explainer", prompt)}
