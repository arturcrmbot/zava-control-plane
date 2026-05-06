"""Concept Fan-out graph (POC3 Phase 4).

  agent_creative_stub -> validate_creative_stub -> terminal

Phase 4 of the creative-campaign orchestrator. v1 stub returns three
concept routes with cached-fixture URLs + brand-fit / distinctiveness
scores. Real implementation in Phase 4 of the plan: `concept-curator`
skill (gpt-5.4) generates three strategic routes; `image_gen` MCP
renders 4 stills per route via Foundry `gpt-image-2`; `brand-guardian`
skill (gpt-4.1-mini) scores each still against the brand-RAG corpus.

Followed by HITL gate ◆2 (concept_lock) where the CD picks the winning
route — see `creative_director` persona's `decision_policy`.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_concept_fanout_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="concept_fanout",
        name="agent_concept_curator",
        executor_type="agent",
        fn=agent_creative_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_concept_fanout",
        name="validate_concept_fanout_schema",
        executor_type="validator",
        fn=validate_creative_stub.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
