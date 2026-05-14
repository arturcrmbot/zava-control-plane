"""End-to-end smoke for autonomous-domain-insights v1 (persona-in-the-loop).

Exercises: persona load with summary_policy → cadence-style summary
handler writes Insight → self-applies via apply_proposed_actions
(matrix-gated) → projection records a Decision → active_policies_for
helper reads it back.

Single test, fully isolated under tmp_path with INSIGHT_LOOP_ENABLED=0
so the cadence loop never auto-fires; the persona is configured under
the cfo role so POL-CFO-001 in the live matrix authorises the
self-apply.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_e2e_one_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")

    from api.server.services.entity_graph import EntityGraph, EntityWrite
    from api.server.state import app_state
    from api.server.routes import insights as insights_route
    route_app_state = insights_route.app_state

    g = EntityGraph(tmp_path / "e2e.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    if route_app_state is not app_state:
        monkeypatch.setattr(route_app_state, "entities", g)

    try:
        from api.server.services import persona_responder as pr

        pdir = tmp_path / "personae"
        fixture = pdir / "cfo"
        fixture.mkdir(parents=True)
        # Tiny CFO fixture that proposes one freeze. Uses the real cfo
        # role so POL-CFO-001 (action=policy_set, category=po,
        # requester_role=cfo) authorises the self-apply.
        skill_md = (
            "---\n"
            "name: cfo\n"
            "description: e2e fixture\n"
            "allowed-tools:\n"
            "workflow_label: Finance\n"
            "external_event: cfo_signoff_decision\n"
            "decision_policy: |\n"
            '    decision = "approve"\n'
            '    reason = "fixture"\n'
            "summary_policy: |\n"
            "    summary = {\n"
            '        "headline": "Fixture proposes freeze",\n'
            '        "body": "",\n'
            '        "kpis": {"acme_pct": 0.9},\n'
            '        "proposed_actions": [{\n'
            '            "id": "act-freeze-acme",\n'
            '            "label": "Freeze Acme POs for 14d",\n'
            '            "kind": "policy_set",\n'
            '            "verdict": "freeze",\n'
            '            "decided_on": ["BRAND-acme"],\n'
            '            "attributes": {"expiry_days": 14, "scope": "po"},\n'
            '            "reason": "fixture",\n'
            "        }],\n"
            '        "fingerprint": "fp-fix-1",\n'
            "    }\n"
            "---\n"
            "\n"
            "# cfo\n"
        )
        (fixture / "SKILL.md").write_text(skill_md, encoding="utf-8")

        monkeypatch.setattr(pr, "PERSONAE_DIR", pdir)
        monkeypatch.setattr(pr, "PERSONA_DEFINITIONS", pr._load_personae())
        assert "cfo" in pr.PERSONA_DEFINITIONS

        g.upsert(EntityWrite(
            kind="Brand", id="BRAND-acme",
            attrs={"name": "Acme"}, source_workflows=(),
        ))

        # Cadence tick → Insight written → self-applies → Decision lands.
        from api.shared.events import FleetEvent

        await pr._handle_summary_request(FleetEvent(
            type="domain.summary.requested",
            payload={"role": "cfo"},
        ))

        # HTTP fetch returns the insight (proves it was written).
        from fastapi.testclient import TestClient
        from api.server.main import app

        client = TestClient(app)
        r = client.get(
            "/api/personas/cfo/insights/latest",
            headers={"x-actor-role": "executive"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["proposed_actions"][0]["id"] == "act-freeze-acme"

        # active_policies_for sees the auto-applied policy WITHOUT any
        # operator click — the matrix authorised, the cadence loop did
        # the rest.
        from api.server.services.policy_lookup import active_policies_for

        policies = active_policies_for(
            app_state.entities,
            scope_kind="Brand",
            scope_id="BRAND-acme",
            verdict="freeze",
        )
        assert len(policies) == 1, policies
        assert policies[0]["persona_role"] == "cfo"
        assert policies[0]["attributes"]["expiry_days"] == 14
        assert policies[0]["attributes"]["governing_rule_id"] == "POL-CFO-001"
    finally:
        g.close()
