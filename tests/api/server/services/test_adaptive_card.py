"""Tests for the Finance-BP Adaptive Card composer (services/adaptive_card.py).

Covers:
- both severity branches (`out_of_envelope` vs `delegation_threshold`),
- stable schema fields (type, $schema, version, zava metadata),
- formatting of GBP figures (thousands separator + signed delta),
- webhook URL composition for each action button.
"""
from __future__ import annotations

from api.server.services.adaptive_card import compose_finance_bp_card


def _common_args(**overrides):
    base = dict(
        workflow_id="WF-FX-001",
        role="Senior Data Engineer",
        cost_centre="CC-1234",
        envelope_remaining_gbp=15_000,
        delta_vs_midpoint_gbp=2_500,
        out_of_envelope=False,
    )
    base.update(overrides)
    return base


def test_compose_returns_adaptive_card_envelope():
    card = compose_finance_bp_card(**_common_args())
    assert card["type"] == "AdaptiveCard"
    assert card["$schema"] == "http://adaptivecards.io/schemas/adaptive-card.json"
    assert card["version"] == "1.5"


def test_zava_metadata_includes_workflow_id_and_card_kind():
    card = compose_finance_bp_card(**_common_args(workflow_id="WF-XYZ-9"))
    meta = card["zava"]
    assert meta["workflow_id"] == "WF-XYZ-9"
    assert meta["card_kind"] == "finance_bp_budget"


def test_severity_delegation_threshold_when_in_envelope():
    card = compose_finance_bp_card(**_common_args(out_of_envelope=False))
    assert card["zava"]["severity"] == "delegation_threshold"
    title = card["body"][0]["text"]
    assert "delegation" in title.lower() or "10k" in title.lower()


def test_severity_out_of_envelope_when_flagged():
    card = compose_finance_bp_card(**_common_args(out_of_envelope=True))
    assert card["zava"]["severity"] == "out_of_envelope"
    title = card["body"][0]["text"]
    assert "out of envelope" in title.lower()


def test_body_includes_role_and_cost_centre():
    card = compose_finance_bp_card(
        **_common_args(role="Principal Engineer", cost_centre="CC-9999")
    )
    texts = [b.get("text", "") for b in card["body"] if b.get("type") == "TextBlock"]
    assert any("Principal Engineer" in t for t in texts)
    assert any("CC-9999" in t for t in texts)


def test_factset_formats_envelope_with_thousands_separator():
    card = compose_finance_bp_card(**_common_args(envelope_remaining_gbp=1_234_567))
    factset = next(b for b in card["body"] if b.get("type") == "FactSet")
    facts = {f["title"]: f["value"] for f in factset["facts"]}
    assert facts["Envelope remaining"] == "£1,234,567"


def test_factset_formats_positive_delta_with_plus_sign():
    card = compose_finance_bp_card(**_common_args(delta_vs_midpoint_gbp=2_500))
    factset = next(b for b in card["body"] if b.get("type") == "FactSet")
    facts = {f["title"]: f["value"] for f in factset["facts"]}
    assert facts["Δ vs band midpoint"] == "£+2,500"


def test_factset_formats_negative_delta_with_minus_sign():
    card = compose_finance_bp_card(**_common_args(delta_vs_midpoint_gbp=-1_500))
    factset = next(b for b in card["body"] if b.get("type") == "FactSet")
    facts = {f["title"]: f["value"] for f in factset["facts"]}
    assert facts["Δ vs band midpoint"] == "£-1,500"


def test_actions_post_to_finance_bp_webhook_with_workflow_id():
    card = compose_finance_bp_card(**_common_args(workflow_id="WF-WEBHOOK"))
    actions = card["actions"]
    assert len(actions) == 3
    titles = [a["title"] for a in actions]
    assert titles == ["Approve", "Reject", "Request more info"]
    decisions = ["approve", "reject", "needs_info"]
    for action, decision in zip(actions, decisions):
        assert action["type"] == "Action.Http"
        assert action["method"] == "POST"
        assert action["url"] == (
            f"/api/webhooks/finance-bp/WF-WEBHOOK?decision={decision}"
        )
