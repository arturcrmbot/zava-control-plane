# src/functions/graphs/screening.py
"""POC2 Phase 5 (Screening) graph.

Spine stub. Track A wires this to the `auto-shortlister` skill emitting a
verdict in {"low", "borderline", "strong"} that drives Phase 6 voice gating
in the orchestrator.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_screening_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_screening", "agent_auto_shortlister", "agent", agent_hiring_stub.execute),
        ("val_screening", "validate_screening_schema", "validator", validate_hiring_stub.execute),
    ])
