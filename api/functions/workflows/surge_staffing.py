"""Surge-staffing orchestrator — a REAL Durable Functions workflow triggered by
the world simulator.

This is the "responder" half of the world-simulator closed loop, proven on the
real Azure Durable Functions runtime (not a mock):

    world engine sensor  ──►  ops.surge_staffing.requested (bus)
                              │
    world_bridge (FastAPI) ──►  schedules THIS orchestration on the func host
                              │   with a snapshot of world state as input
                              ▼
    SurgeStaffingOrchestrator  ──►  surge_staffing_decide_activity ("the agent"
                                    reads the world data and decides how many
                                    agents to hire)
                              │
                              ▼  returns {hired: N}
    world_bridge  ──►  emits surge-staffing.completed(hired=N) on the bus
                       ──►  world engine actuator raises agent capacity
                       ──►  the simulated backlog drains (world changed)

Sync generator per the Azure Durable Functions Python convention; the activity
is registered in ``function_app.py``.
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

import azure.durable_functions as df


def surge_staffing_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """One decision activity: the agent selects reserve workers for the surge."""
    input_dict = context.get_input() or {}
    decision = yield context.call_activity("surge_staffing_decide_activity_trigger", input_dict)
    return {
        "status": "completed",
        "instance_id": context.instance_id,
        "observation": input_dict.get("observation"),
        "command": decision.get("command"),
        "reasoning": decision.get("reasoning"),
    }
