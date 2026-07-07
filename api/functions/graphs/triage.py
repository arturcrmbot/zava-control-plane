# src/functions/graphs/triage.py
"""POC2 Phase 4 (Triage / CV crystallisation) graph.

Spine stub. Track A wires this to the `cv-crystalliser` skill — multimodal
(PDF + LinkedIn JSON + free-text) — per spec §4.8.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_cv_crystalliser
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_triage_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_triage", "agent_cv_crystalliser", "agent", agent_cv_crystalliser.execute),
        ("val_triage", "validate_crystallised_profile_schema", "validator", validate_hiring_stub.execute),
    ])
