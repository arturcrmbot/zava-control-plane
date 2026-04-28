# src/functions/graphs/classify.py
"""Phase 2 (Classify R/A/G) graph for expense claims.

  agent_rag_classifier -> validate_classification_schema_node -> terminal

Per spec §4.1 Phase 2: produce a Red / Amber / Green verdict from the
expense-claim record + retrieved policy context, then guardrail the
classifier payload to spec shape.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_rag_classifier
from api.functions.graphs.executors.validators import validate_classification_schema_node


def build_classify_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="rag_classifier",
        name="agent_rag_classifier",
        executor_type="agent",
        fn=agent_rag_classifier.execute,
    )
    n2 = TrackedExecutor(
        id="val_schema",
        name="validate_classification_schema",
        executor_type="validator",
        fn=validate_classification_schema_node.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
