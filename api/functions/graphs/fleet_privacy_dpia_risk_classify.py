"""Phase 2 (Risk Classify) graph for Privacy DPIA domain."""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.validators import validate_fleet_privacy_dpia_risk_classify_schema


async def _risk_classify_execute(input: dict) -> dict:
    intake = input.get("dpia_intake") or {}
    d = input.get("dpia") or {}
    risk_tier = intake.get("risk_tier") or d.get("risk_tier", "low_risk")
    geography = intake.get("geography") or d.get("geography", "EMEA")
    flags = []
    if risk_tier == "high_risk":
        flags.append("high-risk-processing")
    if geography == "EMEA" and risk_tier == "high_risk":
        flags.append("gdpr-art-35")
    return {
        "ok": True,
        "risk_tier": risk_tier,
        "geography": geography,
        "category": risk_tier,  # matrix uses risk_tier as category
        "flags": flags,
    }


def build_fleet_privacy_dpia_risk_classify_workflow() -> Workflow:
    return build_linear_workflow([
        ("risk_classify", "deterministic_risk_classify", "deterministic", _risk_classify_execute),
        ("val_risk_classify", "validate_risk_classify_schema", "validator", validate_fleet_privacy_dpia_risk_classify_schema.execute),
    ])
