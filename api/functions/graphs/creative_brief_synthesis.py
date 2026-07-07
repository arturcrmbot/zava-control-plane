"""Brief Synthesis graph (POC3 Phase 2).

  agent_creative_stub -> validate_creative_stub -> terminal

Phase 2 of the creative-campaign orchestrator. Takes the voice-intake
transcript (set as `transcript` in the resumed payload by the persona's
brief_capture handler) plus the seed brief record, and projects it into
a structured `brief_json`. v1 stub returns a deterministic projection;
real `brief-synthesiser` skill (gpt-5.4) lands in Phase 4 of
plan/feature-poc3-ai-agency-1.md.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_brief_synthesis_workflow() -> Workflow:
    return build_linear_workflow([
        ("brief_synthesis", "agent_brief_synthesiser", "agent", agent_creative_stub.execute),
        ("val_brief_synthesis", "validate_brief_synthesis_schema", "validator", validate_creative_stub.execute),
    ])
