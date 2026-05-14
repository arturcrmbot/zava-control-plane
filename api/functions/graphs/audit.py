# src/functions/graphs/audit.py
"""Phase 7 (Audit) graph for expense claims.

  agent_audit_summariser -> terminal

Per spec §4.1 Phase 7: compose a one-paragraph compliance summary over
the workflow's existing audit ledger (the orchestrator's
checkpoint_activity calls populate the ledger throughout phases 1-6;
this phase doesn't append new entries — it narrates what's there).
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_audit_summariser


def build_audit_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="audit_summariser",
        name="agent_audit_summariser",
        executor_type="agent",
        fn=agent_audit_summariser.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
