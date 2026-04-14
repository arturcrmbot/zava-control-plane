# src/functions/graphs/executors/validators/validate_gl_active.py
from __future__ import annotations


async def execute(input: dict) -> dict:
    gl = input["gl_decision"]["gl_account_id"]
    active = input["active_gls"]
    return {"ok": gl in active, "blocked_reason": None if gl in active else f"GL {gl} not in active set"}
