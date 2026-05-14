# src/functions/graphs/triage.py
"""POC2 Phase 4 (Triage / CV crystallisation) graph.

Spine stub. Track A wires this to the `cv-crystalliser` skill — multimodal
(PDF + LinkedIn JSON + free-text) — per spec §4.8.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_cv_crystalliser
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_triage_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_triage",
        name="agent_cv_crystalliser",
        executor_type="agent",
        fn=agent_cv_crystalliser.execute,
    )
    n2 = TrackedExecutor(
        id="val_triage",
        name="validate_crystallised_profile_schema",
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
