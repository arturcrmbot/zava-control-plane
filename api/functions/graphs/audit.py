# src/functions/graphs/audit.py
"""Phase 7 (Audit) graph for expense claims.

  agent_audit_summariser -> terminal

Per spec §4.1 Phase 7: compose a one-paragraph compliance summary over
the workflow's existing audit ledger (the orchestrator's
checkpoint_activity calls populate the ledger throughout phases 1-6;
this phase doesn't append new entries — it narrates what's there).
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_audit_summariser


def build_audit_workflow() -> Workflow:
    return build_linear_workflow([
        ("audit_summariser", "agent_audit_summariser", "agent", agent_audit_summariser.execute),
    ])
