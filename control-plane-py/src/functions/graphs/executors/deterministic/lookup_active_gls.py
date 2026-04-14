# src/functions/graphs/executors/deterministic/lookup_active_gls.py
from __future__ import annotations

# Hardcoded for v1 — d365 mock doesn't expose a list endpoint. Bounded-probabilism demo
# case picks GL-9999 which is NOT in this set.
ACTIVE_GLS = ["GL-5000", "GL-5100", "GL-5200"]


async def execute(input: dict) -> dict:
    return {"active_gls": ACTIVE_GLS}
