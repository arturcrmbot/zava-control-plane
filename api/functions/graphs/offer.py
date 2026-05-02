# src/functions/graphs/offer.py
"""POC2 Phase 9 (Offer) graph.

Spine stub. Track A wires this to the `offer-personaliser` skill that
drafts the offer letter; the actual non-revocable send is gated by hooks
(`onPreToolUse`) per spec §4.13. HR BP HITL approval lives at the
orchestrator level (`offer_approval` external event).
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_offer_personaliser
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_offer_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_offer",
        name="agent_offer_personaliser",
        executor_type="agent",
        fn=agent_offer_personaliser.execute,
    )
    n2 = TrackedExecutor(
        id="val_offer",
        name="validate_offer_schema",
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
