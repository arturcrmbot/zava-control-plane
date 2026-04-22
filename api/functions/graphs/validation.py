# src/functions/graphs/validation.py
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.deterministic import three_way_match


def build_validation_workflow() -> Workflow:
    n1 = TrackedExecutor(id="three_way_match", name="three_way_match",
                         executor_type="deterministic", fn=three_way_match.execute)
    term = TerminalExecutor(id="terminal")
    return WorkflowBuilder(start_executor=n1).add_edge(n1, term).build()
