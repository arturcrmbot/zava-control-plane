"""HTTP surface for ambient agents per function — Phase 4 IP7 (TASK-033c).

`GET /api/functions/{function_name}/ambient` returns a list of
`AmbientAgent` records for that function with their last-trigger /
last-spawn-outcome state pulled from the dispatcher's per-agent ring
buffer, plus a kill-switch flag. The blueprint /admin/org-clone page
fans this endpoint out across all 9 non-legacy functions.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from api.server.services.ambient_agents import (
    AMBIENT_AGENTS,
    BusTrigger,
    CadenceTrigger,
    CypherTrigger,
)
from api.server.services.governance.kill_switch import kill_switch_store
from api.server.state import app_state
from api.shared.functions import FUNCTIONS

router = APIRouter(prefix="/api/functions")


def _trigger_dict(t: Any) -> dict:
    if isinstance(t, BusTrigger):
        return {"kind": "bus", "event_type": t.event_type, "filter": t.filter}
    if isinstance(t, CypherTrigger):
        return {"kind": "cypher", "pattern": t.pattern,
                "sweep_seconds": t.sweep_seconds}
    if isinstance(t, CadenceTrigger):
        return {"kind": "cadence", "cron": t.cron}
    return {"kind": "unknown"}


def _last_state(agent_name: str) -> tuple[float | None, dict | None]:
    """Pull (last_trigger_at, last_spawn_outcome) from the dispatcher ring."""
    dispatcher = getattr(app_state, "ambient_dispatcher", None)
    if dispatcher is None:
        return None, None
    try:
        state = dispatcher.get_state(agent_name)
    except Exception:
        return None, None
    recent = state.get("recent") or []
    # Walk backwards looking for an entry that carries a real spawn
    # outcome (the cadence-registration entries do not).
    for entry in reversed(recent):
        outcome = entry.get("spawn_outcome") if isinstance(entry, dict) else None
        if outcome is not None:
            ts = entry.get("timestamp") or entry.get("at")
            return ts, outcome
    return None, None


@router.get("/{function_name}/ambient")
async def function_ambient(function_name: str):
    if function_name == "legacy" or function_name not in FUNCTIONS:
        raise HTTPException(status_code=404,
                            detail=f"unknown function: {function_name}")
    out: list[dict] = []
    for agent in AMBIENT_AGENTS.values():
        if agent.function != function_name:
            continue
        last_ts, last_outcome = _last_state(agent.name)
        is_killed = kill_switch_store.is_killed(
            f"ambient.{agent.name}", "spawn_workflow",
        ) is not None
        out.append({
            "name": agent.name,
            "function": agent.function,
            "triggers": [_trigger_dict(t) for t in agent.triggers],
            "spawnable_workflow_types": list(agent.spawnable_workflow_types),
            "reasoning_skill": agent.reasoning_skill,
            "last_trigger_at": last_ts,
            "last_spawn_outcome": last_outcome,
            "is_killed": is_killed,
        })
    return out
