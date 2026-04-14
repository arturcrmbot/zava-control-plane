# src/functions/graphs/executors/agents/agent_anomaly_flagger.py
from __future__ import annotations
import json
from ._wrapper import run_agent_skill


async def execute(input: dict) -> dict:
    extracted = input["extracted"]
    vendor = input["vendor"]
    prompt = (
        f"Vendor:\n{json.dumps(vendor)}\n\n"
        f"Extracted invoice:\n{json.dumps(extracted)}\n\n"
        f"Assess anomalies per your role."
    )
    result = await run_agent_skill("anomaly_flagger", prompt)
    return {"anomaly": result, "extracted": extracted}
