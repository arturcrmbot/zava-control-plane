"""Concept Fan-out graph (POC3 Phase 4).

  agent_creative_stub -> validate_brand_guardian -> terminal

Phase 4 of the creative-campaign orchestrator. v1 stub returns three
concept routes with cached-fixture URLs. Phase 2 of the plan adds
`brand-guardian` as the validator: it reads the brand corpus,
queries `query_brand_corpus` once per route, and overlays
brand_fit / distinctiveness / violations on top of the agent's draft
scores.

Phase 4 of the plan replaces the agent stub with a real
`concept-curator` skill (gpt-5.4) that generates three strategic
routes; `image_gen` MCP renders 4 stills per route via Foundry
`gpt-image-2`. brand-guardian (Phase 2) stays as the validator —
the same code applies whether the routes were stubbed or rendered
for real.

Followed by HITL gate ◆2 (concept_lock) where the CD picks the
winning route — see `creative_director` persona's `decision_policy`.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_brand_guardian


def build_creative_concept_fanout_workflow() -> Workflow:
    return build_linear_workflow([
        ("concept_fanout", "agent_concept_curator", "agent", agent_creative_stub.execute),
        ("val_brand_guardian_concept", "agent_brand_guardian", "agent", validate_brand_guardian.execute),
    ])
