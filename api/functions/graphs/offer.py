# src/functions/graphs/offer.py
"""POC2 Phase 9 (Offer) graph.

Spine stub. Track A wires this to the `offer-personaliser` skill that
drafts the offer letter; the actual non-revocable send is gated by hooks
(`onPreToolUse`) per spec §4.13. HR BP HITL approval lives at the
orchestrator level (`offer_approval` external event).
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_offer_personaliser
from api.functions.graphs.executors.validators import validate_hiring_stub


def build_hiring_offer_workflow() -> Workflow:
    return build_linear_workflow([
        ("hiring_offer", "agent_offer_personaliser", "agent", agent_offer_personaliser.execute),
        ("val_offer", "validate_offer_schema", "validator", validate_hiring_stub.execute),
    ])
