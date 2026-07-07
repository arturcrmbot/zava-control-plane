# src/functions/graphs/intake.py
"""
Intake graph (hybrid):
  doc_intelligence_extract -> agent_field_extractor -> agent_line_item_extractor
    -> validate_required_fields -> agent_anomaly_flagger -> validate_amount_consistency
    -> terminal
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.deterministic import doc_intelligence_extract
from api.functions.graphs.executors.agents import (
    agent_field_extractor, agent_line_item_extractor, agent_anomaly_flagger,
)
from api.functions.graphs.executors.validators import (
    validate_required_fields, validate_amount_consistency,
)


def build_intake_workflow() -> Workflow:
    return build_linear_workflow([
        ("doc_intel", "doc_intelligence_extract", "deterministic", doc_intelligence_extract.execute),
        ("field_ext", "agent_field_extractor", "agent", agent_field_extractor.execute),
        ("line_ext", "agent_line_item_extractor", "agent", agent_line_item_extractor.execute),
        ("val_req", "validate_required_fields", "validator", validate_required_fields.execute),
        ("anomaly", "agent_anomaly_flagger", "agent", agent_anomaly_flagger.execute),
        ("val_amt", "validate_amount_consistency", "validator", validate_amount_consistency.execute),
    ])
