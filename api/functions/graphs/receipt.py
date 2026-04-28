# src/functions/graphs/receipt.py
"""Phase 3 (Validate Receipt) graph for expense claims.

  agent_receipt_validator -> validate_receipt_schema -> terminal

Per spec §4.1 Phase 3: multimodal cross-check the attached receipt image
against the claim's structured fields, classify any mismatch flavour, then
guardrail the payload to the spec shape.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_receipt_validator
from api.functions.graphs.executors.validators import validate_receipt_schema


def build_receipt_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="receipt_validator",
        name="agent_receipt_validator",
        executor_type="agent",
        fn=agent_receipt_validator.execute,
    )
    n2 = TrackedExecutor(
        id="val_receipt_schema",
        name="validate_receipt_schema",
        executor_type="validator",
        fn=validate_receipt_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
