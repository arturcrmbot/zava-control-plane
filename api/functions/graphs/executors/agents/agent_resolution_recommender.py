# src/functions/graphs/executors/agents/agent_resolution_recommender.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    item = input["unmatched_item"]
    classification = input["exception_classification"]
    root_cause = input["root_cause"]
    workflow_id = input.get("workflow_id")
    prompt = (
        f"Item: {json.dumps(item)}\n"
        f"Classification: {json.dumps(classification)}\n"
        f"Root cause: {json.dumps(root_cause)}\n\n"
        f"Recommend per your role."
    )
    return {"resolution_recommendation": await run_agent_skill("resolution_recommender", prompt, workflow_id=workflow_id)}
