"""Test the privacy-dpia projection (TASK-024)."""
from __future__ import annotations

import json

from api.server.services.entity_graph import DecisionWrite, EntityWrite
from api.server.services.entity_projections.privacy_dpia import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_privacy_dpia_projection_emits_dpia_asset_and_region_place():
    payload = fixture_payload("privacy-dpia", "dpias.json")
    wf = make_workflow("DPI-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Asset", "Place"} <= kinds
    asset = next(e for e in entities if e.kind == "Asset")
    assert asset.attrs["kind"] == "dpia"
    # ``risk_tier`` is not an Asset schema column — lives in attributes JSON.
    asset_extra = json.loads(asset.attrs["attributes"])
    assert asset_extra["risk_tier"] == payload["risk_tier"]


def test_privacy_dpia_projection_emits_cpo_decision_only_for_high_risk():
    payload_low = fixture_payload("privacy-dpia", "dpias.json")
    decisions_template = [
        {"phase": "privacy_dpo_review", "verdict": "approve", "reason": "ok",
         "decided_at": "2026-06-01T10:00:00+00:00"},
        {"phase": "privacy_cpo_signoff", "verdict": "approve", "reason": "ok",
         "decided_at": "2026-06-02T10:00:00+00:00"},
    ]
    wf_low = make_workflow("DPI-T2", WORKFLOW_TYPE, payload_low,
                           decisions=decisions_template)
    low_decisions = [o for o in project(wf_low) if isinstance(o, DecisionWrite)]
    assert len(low_decisions) == 1  # CPO gate not active for low_risk

    payload_high = dict(payload_low)
    payload_high["risk_tier"] = "high"
    wf_high = make_workflow("DPI-T3", WORKFLOW_TYPE, payload_high,
                            decisions=decisions_template)
    high_decisions = [o for o in project(wf_high) if isinstance(o, DecisionWrite)]
    assert len(high_decisions) == 2
