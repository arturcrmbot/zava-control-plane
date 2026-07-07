"""Phase 3 (Calibration Drafter) graph for Performance review.

  agent_calibration_drafter -> validate_fleet_perf_review_calibration_drafter_schema -> terminal

Per brief: agent drafts a proposed rating + narrative by combining the
cycle's OKR results with the grade-band distribution norm and the
reviewee's calibration history. Validator guardrails the agent payload
so the HR persona policy can rely on `distribution_fit` taking a
known value.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_perf_review_calibration_drafter
from api.functions.graphs.executors.validators import validate_fleet_perf_review_calibration_drafter_schema


def build_fleet_perf_review_calibration_drafter_workflow() -> Workflow:
    return build_linear_workflow([
        ("calibration_drafter", "agent_calibration_drafter", "agent", agent_fleet_perf_review_calibration_drafter.execute),
        ("val_calibration_drafter", "validate_fleet_perf_review_calibration_drafter_schema", "validator", validate_fleet_perf_review_calibration_drafter_schema.execute),
    ])
