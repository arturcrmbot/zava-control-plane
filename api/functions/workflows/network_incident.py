"""Durable responder that turns a network anomaly into a typed command.

The orchestration receives the failed site, its healthy neighbours (with spare
capacity) and the affected sessions from the authoritative simulation. Its
single activity greedily assigns each degraded session to a neighbour with room
and returns a ``reroute_sessions`` command. FastAPI's world bridge validates
and applies that command to the real session actors.
"""
from __future__ import annotations

from collections.abc import Generator
from typing import Any

import azure.durable_functions as df


def network_incident_orchestration(
    context: df.DurableOrchestrationContext,
) -> Generator[Any, Any, dict]:
    """One decision activity: the agent reroutes sessions off the failed site."""
    input_dict = context.get_input() or {}
    decision = yield context.call_activity(
        "network_incident_decide_activity_trigger", input_dict
    )
    return {
        "status": "completed",
        "instance_id": context.instance_id,
        "observation": input_dict.get("observation"),
        "command": decision.get("command"),
        "reasoning": decision.get("reasoning"),
    }
