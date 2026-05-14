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
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_escalation
from api.functions.graphs.executors.deterministic import apply_verdict_routing


def build_route_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="escalation_advisor",
        name="agent_escalation",
        executor_type="agent",
        fn=agent_escalation.execute,
    )
    n2 = TrackedExecutor(
        id="route_by_verdict",
        name="apply_verdict_routing",
        executor_type="deterministic",
        fn=apply_verdict_routing.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
