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
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_brief_synthesis_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="brief_synthesis",
        name="agent_brief_synthesiser",
        executor_type="agent",
        fn=agent_creative_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_brief_synthesis",
        name="validate_brief_synthesis_schema",
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
