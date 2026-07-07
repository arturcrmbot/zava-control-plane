# src/functions/graphs/intake_expense.py
"""Phase 1 (Intake & Normalise) graph for expense claims.

  lookup_claim -> doc_intelligence_extract -> agent_field_extractor -> validate_required_fields

Per spec §4.1: pull claim from EMS (Workday or Concur), normalise to common
schema, OCR receipt. Skips the invoice-only line-item / anomaly-flagger nodes.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.deterministic import (
    lookup_claim,
    doc_intelligence_extract,
)
from api.functions.graphs.executors.agents import agent_field_extractor
from api.functions.graphs.executors.validators import validate_required_fields


def build_intake_expense_workflow() -> Workflow:
    return build_linear_workflow([
        ("lookup", "lookup_claim", "deterministic", lookup_claim.execute),
        ("doc_intel", "doc_intelligence_extract", "deterministic", doc_intelligence_extract.execute),
        ("field_ext", "agent_field_extractor", "agent", agent_field_extractor.execute),
        ("val_req", "validate_required_fields", "validator", validate_required_fields.execute),
    ])
