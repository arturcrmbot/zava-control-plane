"""Phase 2 (Peer Feedback Aggregator) graph for Performance review.

  agent_peer_feedback_aggregator -> validate_fleet_perf_review_peer_feedback_aggregator_schema -> terminal

Per brief: agent collects 360-degree peer reviews for the cycle,
re-confirms the reviewee's reporting line via Workday HR, and pulls the
cycle's OKR results from the feedback collector. Validator guardrails
the agent payload to the spec shape so Phase 3 (and the HR persona) can
rely on a stable peer_review_count.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_perf_review_peer_feedback_aggregator
from api.functions.graphs.executors.validators import validate_fleet_perf_review_peer_feedback_aggregator_schema


def build_fleet_perf_review_peer_feedback_aggregator_workflow() -> Workflow:
    return build_linear_workflow([
        ("peer_feedback_aggregator", "agent_peer_feedback_aggregator", "agent", agent_fleet_perf_review_peer_feedback_aggregator.execute),
        ("val_peer_feedback_aggregator", "validate_fleet_perf_review_peer_feedback_aggregator_schema", "validator", validate_fleet_perf_review_peer_feedback_aggregator_schema.execute),
    ])
