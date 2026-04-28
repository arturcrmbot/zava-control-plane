# src/functions/graphs/onboarding.py
"""POC2 Phase 10 (Onboarding) graph.

Spine stub. Track C wires this to the `onboarding-buddy` skill calling
`heygen_render` (avatar) + `servicenow_jml` (provisioning) + `graph_invite`
(day-1 calendar) per spec §4.5 + §4.13. Hook-gated for the JML send.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_onboarding_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_onboarding",
        name="agent_onboarding_buddy",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_onboarding",
        name="validate_onboarding_schema",
        executor_type="validator",
        fn=validate_hiring_stub.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
