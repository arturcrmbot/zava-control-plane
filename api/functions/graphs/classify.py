# src/functions/graphs/classify.py
"""Phase 2 (Classify R/A/G) graph for expense claims.

  agent_rag_classifier -> validate_classification_schema_node -> terminal

Per spec §4.1 Phase 2: produce a Red / Amber / Green verdict from the
expense-claim record + retrieved policy context, then guardrail the
classifier payload to spec shape.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_rag_classifier
from api.functions.graphs.executors.validators import validate_classification_schema_node


def build_classify_workflow() -> Workflow:
    return build_linear_workflow([
        ("rag_classifier", "agent_rag_classifier", "agent", agent_rag_classifier.execute),
        ("val_schema", "validate_classification_schema", "validator", validate_classification_schema_node.execute),
    ])
