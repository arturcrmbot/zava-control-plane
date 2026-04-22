# src/functions/graphs/executors/agents/agent_exception_classifier.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    prompt = (
        f"Unmatched item: {json.dumps(item)}\n\n"
        f"Classify per your role."
    )
    return {"exception_classification": await run_agent_skill("exception_classifier", prompt)}
