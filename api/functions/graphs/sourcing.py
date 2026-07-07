# src/functions/graphs/sourcing.py
"""POC2 Phase 3 (Sourcing) graph.

Spine stub. Track A wires this to the `sourcing-orchestrator` skill that
fans out to `linkedin_search` + `greenhouse_post`.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_sourcing_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_sourcing", "agent_sourcing_orchestrator", "agent", agent_hiring_stub.execute),
        ("val_sourcing", "validate_sourcing_schema", "validator", validate_hiring_stub.execute),
    ])
