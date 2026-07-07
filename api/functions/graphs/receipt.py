# src/functions/graphs/receipt.py
"""Phase 3 (Validate Receipt) graph for expense claims.

  agent_receipt_validator -> validate_receipt_schema -> terminal

Per spec §4.1 Phase 3: multimodal cross-check the attached receipt image
against the claim's structured fields, classify any mismatch flavour, then
guardrail the payload to the spec shape.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_receipt_validator
from api.functions.graphs.executors.validators import validate_receipt_schema


def build_receipt_workflow() -> Workflow:
    return build_linear_workflow([
        ("receipt_validator", "agent_receipt_validator", "agent", agent_receipt_validator.execute),
        ("val_receipt_schema", "validate_receipt_schema", "validator", validate_receipt_schema.execute),
    ])
