"""Durable responder that turns actor-level pressure into a typed command.

The orchestration receives queued tickets, active workers and reserve workers
from the authoritative simulation. Its activity selects actual reserve worker
IDs by skill pressure and returns a ``reallocate_workers`` command. FastAPI's
world bridge validates and applies that command to the real worker actors.
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
