# src/functions/graphs/executors/agents/agent_field_extractor.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    raw = input["raw_text"]
    structure = input["structure"]
    prompt = (
        f"Raw invoice payload:\n{raw}\n\n"
        f"Structure hints:\n{json.dumps(structure)}\n\n"
        f"Return the structured fields as JSON per your role."
    )
    extracted = await run_agent_skill("field_extractor", prompt)

    # Sub-agent delegation: for any field marked needs_subagent, spawn a sub-session
    # focused on just that field. Visible in right rail as nested invocations.
    if isinstance(extracted, dict):
        for field, value in list(extracted.items()):
            if isinstance(value, dict) and value.get("needs_subagent"):
                sub_prompt = (
                    f"Resolve the value of field '{field}' from this invoice context: {raw}. "
                    f"Best guess so far: {value.get('value')}. "
                    f"Confidence: {value.get('confidence')}. "
                    f"Return JSON with just {{\"value\": <resolved>, \"confidence\": <float>}}."
                )
                sub_result = await run_agent_skill("field_extractor", sub_prompt)
                extracted[field] = sub_result.get("value", value.get("value"))

    return {"extracted": extracted}
