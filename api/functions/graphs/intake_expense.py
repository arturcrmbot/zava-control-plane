# src/functions/graphs/intake_expense.py
"""Phase 1 (Intake & Normalise) graph for expense claims.

  lookup_claim -> doc_intelligence_extract -> agent_field_extractor -> validate_required_fields

Per spec §4.1: pull claim from EMS (Workday or Concur), normalise to common
schema, OCR receipt. Skips the invoice-only line-item / anomaly-flagger nodes.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.deterministic import (
    lookup_claim,
    doc_intelligence_extract,
)
from api.functions.graphs.executors.agents import agent_field_extractor
from api.functions.graphs.executors.validators import validate_required_fields


def build_intake_expense_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="lookup",
        name="lookup_claim",
        executor_type="deterministic",
        fn=lookup_claim.execute,
    )
    n2 = TrackedExecutor(
        id="doc_intel",
        name="doc_intelligence_extract",
        executor_type="deterministic",
        fn=doc_intelligence_extract.execute,
    )
    n3 = TrackedExecutor(
        id="field_ext",
        name="agent_field_extractor",
        executor_type="agent",
        fn=agent_field_extractor.execute,
    )
    n4 = TrackedExecutor(
        id="val_req",
        name="validate_required_fields",
        executor_type="validator",
        fn=validate_required_fields.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, n3)
        .add_edge(n3, n4)
        .add_edge(n4, term)
        .build()
    )
