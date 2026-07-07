# src/functions/graphs/arbitrate.py
"""Phase 6 (Arbitrate) graph for expense claims.

  agent_arbitration -> validate_arbitration_schema -> terminal

Per spec §4.1 Phase 6: SSC reviewer arbitration on Red claims after the
claimant justification round-trip from Phase 5. Recommends one of
accept-justification / require-repayment / issue-warning / escalate
with a cited precedent.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_arbitration
from api.functions.graphs.executors.validators import validate_arbitration_schema


def build_arbitrate_workflow() -> Workflow:
    return build_linear_workflow([
        ("arbitration", "agent_arbitration", "agent", agent_arbitration.execute),
        ("val_arb_schema", "validate_arbitration_schema", "validator", validate_arbitration_schema.execute),
    ])
