"""Phase 2 (Peer Feedback Aggregator) graph for Performance review.

  agent_peer_feedback_aggregator -> validate_fleet_perf_review_peer_feedback_aggregator_schema -> terminal

Per brief: agent collects 360-degree peer reviews for the cycle,
re-confirms the reviewee's reporting line via Workday HR, and pulls the
cycle's OKR results from the feedback collector. Validator guardrails
the agent payload to the spec shape so Phase 3 (and the HR persona) can
rely on a stable peer_review_count.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_perf_review_peer_feedback_aggregator
from api.functions.graphs.executors.validators import validate_fleet_perf_review_peer_feedback_aggregator_schema


def build_fleet_perf_review_peer_feedback_aggregator_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="peer_feedback_aggregator",
        name="agent_peer_feedback_aggregator",
        executor_type="agent",
        fn=agent_fleet_perf_review_peer_feedback_aggregator.execute,
    )
    n2 = TrackedExecutor(
        id="val_peer_feedback_aggregator",
        name="validate_fleet_perf_review_peer_feedback_aggregator_schema",
        executor_type="validator",
        fn=validate_fleet_perf_review_peer_feedback_aggregator_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
