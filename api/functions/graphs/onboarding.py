# src/functions/graphs/onboarding.py
"""POC2 Phase 10 (Onboarding) graph.

Calls the `onboarding-buddy` skill family: `avatar_render` (Azure AI Speech
batch avatar) + `servicenow_jml` (provisioning) + `graph_invite` (day-1
calendar) per spec §4.5 + §4.13. The avatar render result lands on
`workflow.metadata.onboarding_video_url` so the candidate portal can replay
it. Hook-gated for the JML send (deferred to subsequent stream).
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_onboarding
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_onboarding_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_onboarding", "agent_onboarding_buddy", "agent", agent_onboarding.execute),
        ("val_onboarding", "validate_onboarding_schema", "validator", validate_hiring_stub.execute),
    ])
