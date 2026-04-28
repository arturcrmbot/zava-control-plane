# src/functions/graphs/voice.py
"""POC2 Phase 6 (Voice screening) graph.

Spine stub. Track C wires this to the `voice-screener` skill calling
`acs_dial` + `transcript_score` per spec §4.5. ACS / GPT-Realtime stubbed
locally via `acs-mcp`.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_hiring_stub
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_voice_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="hiring_voice",
        name="agent_voice_screener",
        executor_type="agent",
        fn=agent_hiring_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_voice",
        name="validate_voice_transcript_schema",
        executor_type="validator",
        fn=validate_hiring_stub.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
