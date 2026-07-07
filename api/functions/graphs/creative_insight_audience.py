"""Insight & Audience graph (POC3 Phase 3).

  agent_creative_stub -> validate_creative_stub -> terminal

Phase 3 of the creative-campaign orchestrator. Three agents fan out
in parallel in the real implementation (audience-clusterer, trend-scanner,
brand-knowledge); v1 stub returns a single deterministic merged payload
so downstream phases have something to read. No HITL gate on this phase
— supervisor watches via the existing AgentReasoningTimeline component.
Real fan-out lands in Phase 4 of plan/feature-poc3-ai-agency-1.md.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_insight_audience_workflow() -> Workflow:
    return build_linear_workflow([
        ("insight_audience", "agent_insight_audience", "agent", agent_creative_stub.execute),
        ("val_insight_audience", "validate_insight_audience_schema", "validator", validate_creative_stub.execute),
    ])
