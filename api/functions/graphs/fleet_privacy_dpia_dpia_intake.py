"""Phase 1 (DPIA Intake) graph for Privacy DPIA domain."""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow


async def _dpia_intake_execute(input: dict) -> dict:
    d = input.get("dpia") or {}
    dpia_id = d.get("dpia_id")
    if not dpia_id:
        return {"ok": False, "blocked_reason": "missing dpia.dpia_id"}
    return {
        "ok": True,
        "dpia_id": dpia_id,
        "system_name": d.get("system_name", "Unnamed System"),
        "risk_tier": d.get("risk_tier", "low_risk"),
        "geography": d.get("geography", "EMEA"),
    }


def build_fleet_privacy_dpia_dpia_intake_workflow() -> Workflow:
    return build_linear_workflow([
        ("dpia_intake", "deterministic_dpia_intake", "deterministic", _dpia_intake_execute),
    ])
