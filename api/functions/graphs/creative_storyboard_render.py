"""Storyboard Render graph (POC3 Phase 5).

  agent_creative_stub -> validate_creative_stub -> terminal

Phase 5 of the creative-campaign orchestrator. v1 stub returns 6
cached-fixture URLs + frame captions. Real implementation in Phase 4
of the plan: `storyboard-curator` skill (gpt-5.4) takes the locked
route + brief, generates 6 storyboard frame prompts, then calls
`image_gen.generate_concept_stills(...)` × 6 via Foundry `gpt-image-2`.

Followed by HITL gate ◆3 (storyboard_approval) and ◆4 (final_signoff).
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_storyboard_render_workflow() -> Workflow:
    return build_linear_workflow([
        ("storyboard_render", "agent_storyboard_curator", "agent", agent_creative_stub.execute),
        ("val_storyboard_render", "validate_storyboard_render_schema", "validator", validate_creative_stub.execute),
    ])
