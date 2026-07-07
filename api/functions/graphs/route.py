# src/functions/graphs/route.py
"""Phase 4 (Route by Verdict) graph for expense claims.

  agent_escalation -> apply_verdict_routing -> terminal

Per spec §4.1 Phase 4: green claims auto-close; amber go to the SSC reviewer
queue; red proceed to Phase 5 (Notify). The escalation advisor runs in line
on amber/red to set the progressive-enforcement tier; it short-circuits to
no-op on green. The deterministic router uses verdict + tier to pick the
downstream path, with optional runtime override from the policy page.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_escalation
from api.functions.graphs.executors.deterministic import apply_verdict_routing


def build_route_workflow() -> Workflow:
    return build_linear_workflow([
        ("escalation_advisor", "agent_escalation", "agent", agent_escalation.execute),
        ("route_by_verdict", "apply_verdict_routing", "deterministic", apply_verdict_routing.execute),
    ])
