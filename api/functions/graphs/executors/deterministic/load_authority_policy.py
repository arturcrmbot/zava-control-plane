# src/functions/graphs/executors/deterministic/load_authority_policy.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    return {"auto_threshold": 5000.0, "cfo_threshold": 25000.0}
