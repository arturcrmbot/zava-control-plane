"""Surge-staffing decision activity — "the agent" in the world-simulator loop.

Runs as an Azure Durable Functions activity on the func host. It receives a
snapshot of the *simulated world* (support backlog, arrival rate, current agent
capacity, service rate per agent) and decides how many agents to hire so the
world recovers. The decision is a deterministic function of the world data —
no external model call — so the proof is reproducible, but it is genuinely
data-driven: change the world, the decision changes.

Sizing rule: raise capacity so the service rate (agents * HANDLE) covers both
the current arrival rate and burns down the accumulated backlog, i.e.
    target_agents = ceil((backlog + arrival) / HANDLE)
    hired         = max(0, target_agents - current_agents)   # capped
"""
from __future__ import annotations

import math


def surge_staffing_decide_activity(payload: dict) -> dict:
    world = payload.get("world") or {}
    backlog = float(world.get("backlog", 0.0))
    arrival = float(world.get("arrival", 0.0))
    handle = float(world.get("handle", 0.0)) or 1.0
    agents = float(world.get("agents", 0.0))

    target_agents = math.ceil((backlog + arrival) / handle)
    hired = max(0, min(200, target_agents - int(agents)))

    return {
        "hired": hired,
        "target_agents": target_agents,
        "reasoning": (
            f"world backlog={backlog:.0f}, arrival={arrival:.0f}/h, "
            f"HANDLE={handle:.0f}/agent, agents={agents:.0f} "
            f"-> target {target_agents} agents, hire {hired}"
        ),
    }
