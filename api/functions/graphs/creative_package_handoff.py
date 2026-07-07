"""Package & Handoff graph (POC3 Phase 6).

  agent_creative_stub -> validate_creative_stub -> terminal

Phase 6 of the creative-campaign orchestrator. The closing phase. v1
stub returns a placeholder `figma_file_url`; real implementation in
Phase 6 of the plan: the `figma` MCP pushes the locked-route stills +
storyboard frames + brief PDF as a new page in the shared demo Figma
file, then the orchestrator stamps the real Figma page URL onto
`workflow.payload.figma_file_url`.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_package_handoff_workflow() -> Workflow:
    return build_linear_workflow([
        ("package_handoff", "agent_package_handoff", "agent", agent_creative_stub.execute),
        ("val_package_handoff", "validate_package_handoff_schema", "validator", validate_creative_stub.execute),
    ])
