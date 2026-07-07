# src/functions/graphs/compliance.py
"""POC2 Phase 8 (Compliance) graph.

Spine stub. Track D wires this to the `jurisdiction-router` skill which
fans out to `betrvg-checker` (DE only) per spec §4.10. USA path is a
no-op compliance summary; DE path adds works-council notification.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_compliance_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_compliance", "agent_jurisdiction_router", "agent", agent_hiring_stub.execute),
        ("val_compliance", "validate_compliance_schema", "validator", validate_hiring_stub.execute),
    ])
