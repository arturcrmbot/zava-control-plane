"""Phase 5.2 of autonomous-domain-insights v1: policy_set projection."""
from __future__ import annotations

from api.server.services.entity_projections import PROJECTIONS

from ._helpers import make_workflow


def test_policy_set_in_registry():
    assert "policy_set" in PROJECTIONS


def test_projection_emits_decision_with_verdict_and_targets():
    project = PROJECTIONS["policy_set"]
    wf = make_workflow(
        "WF-POL-1",
        "policy_set",
        {
            "decisions": [
                {
                    "phase": "policy_set",
                    "verdict": "freeze",
                    "reason": "CFO action approved",
                    "decided_at": "2026-05-12T10:00:00Z",
                    "persona_role": "cfo",
                },
            ],
            "persona_role": "cfo",
            "decided_on": ["BRAND-acme"],
            "attributes": {"expiry_days": 14, "scope": "po"},
            "verdict": "freeze",
        },
    )
    out = project(wf)
    decisions = [w for w in out if w.__class__.__name__ == "DecisionWrite"]
    assert len(decisions) == 1
    d = decisions[0]
    assert d.phase == "policy_set"
    assert d.verdict == "freeze"
    assert d.persona_role == "cfo"
    assert d.decided_on == ("BRAND-acme",)
    assert d.attributes["expiry_days"] == 14


def test_projection_returns_empty_when_no_decisions_in_payload():
    project = PROJECTIONS["policy_set"]
    wf = make_workflow("WF-POL-2", "policy_set", {})
    assert project(wf) == []


def test_projection_canonicalises_verdict_aliases():
    project = PROJECTIONS["policy_set"]
    wf = make_workflow(
        "WF-POL-3",
        "policy_set",
        {
            "decisions": [{
                "phase": "policy_set",
                "verdict": "frozen",
                "reason": "alias path",
                "decided_at": "2026-05-12T10:00:00Z",
                "persona_role": "cfo",
            }],
            "persona_role": "cfo",
            "decided_on": ["BRAND-acme"],
            "verdict": "frozen",
        },
    )
    out = project(wf)
    decisions = [w for w in out if w.__class__.__name__ == "DecisionWrite"]
    assert decisions[0].verdict == "freeze"
