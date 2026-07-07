# src/functions/graphs/job_design.py
"""POC2 Phase 2 (Job Design) graph.

Spine stub. Track A replaces the agent with the `jd-drafter` skill, which
calls `policy_search` for jurisdiction-appropriate JD boilerplate.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_job_design_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_job_design", "agent_jd_drafter", "agent", agent_hiring_stub.execute),
        ("val_jd", "validate_jd_schema", "validator", validate_hiring_stub.execute),
    ])
