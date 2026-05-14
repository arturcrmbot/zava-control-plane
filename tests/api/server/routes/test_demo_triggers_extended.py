"""Tests for Phase H2 extended /api/demo/trigger/* routes.

Covers the three new persona-targeted scenarios:

* ``POST /api/demo/trigger/fx-exposure``        — Treasurer
* ``POST /api/demo/trigger/vendor-concentration`` — Sourcing Lead
* ``POST /api/demo/trigger/department-attrition`` — HR Director

Mirrors the fixture pattern in ``test_demo_triggers.py``: build a fresh
on-disk Kuzu graph in ``tmp_path`` and ``monkeypatch.setattr`` it onto
``app_state.entities`` so the routes mutate the test graph rather than
the process-wide one.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.state import app_state


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("INSIGHT_LOOP_ENABLED", "0")
    g = EntityGraph(tmp_path / "ig.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    try:
        from api.server.main import app
        yield TestClient(app), g
    finally:
        g.close()


HDRS = {"x-actor-role": "executive"}


# ---------------------------------------------------------------------------
# fx-exposure
# ---------------------------------------------------------------------------


def test_fx_exposure_inserts_treasury_decisions(client):
    c, g = client

    r = c.post("/api/demo/trigger/fx-exposure", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["currency_pair"] == "EUR/GBP"
    assert len(body["decisions_inserted"]) == 5
    assert body["before_total"] == 0.0
    assert body["after_total"] == pytest.approx(10_800_000.0)
    assert body["total_notional_gbp_added"] == pytest.approx(10_800_000.0)
    assert body["after_total"] > 8_000_000.0  # trips Treasurer threshold

    rows = g.query(
        "MATCH (d:Decision) WHERE d.phase = 'treasury_signoff' "
        "AND d.currency_pair = 'EUR/GBP' "
        "RETURN d.id AS id, d.notional_gbp AS notional, "
        "       d.persona_role AS role, d.verdict AS verdict"
    )
    assert len(rows) == 5
    for row in rows:
        assert row["role"] == "treasurer"
        assert row["verdict"] == "approve"
        notional = float(row["notional"])
        assert 1_500_000.0 <= notional <= 3_000_000.0


def test_fx_exposure_compounds_on_repeat_calls(client):
    c, g = client

    c.post("/api/demo/trigger/fx-exposure", headers=HDRS).raise_for_status()
    r2 = c.post("/api/demo/trigger/fx-exposure", headers=HDRS)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["before_total"] == pytest.approx(10_800_000.0)
    assert body["after_total"] == pytest.approx(21_600_000.0)


# ---------------------------------------------------------------------------
# vendor-concentration
# ---------------------------------------------------------------------------


def _seed_vendor(g: EntityGraph, *, vendor_id: str, name: str) -> None:
    g.upsert(EntityWrite(
        kind="Organisation",
        id=vendor_id,
        attrs={"name": name, "kind": "vendor", "risk_band": "green"},
        source_workflows=(),
    ))


def _seed_money_pays(g: EntityGraph, *, money_id: str, amount: float, vendor_id: str) -> None:
    g.upsert(EntityWrite(
        kind="Money",
        id=money_id,
        attrs={"amount": float(amount), "currency": "GBP", "kind": "po"},
        source_workflows=(),
    ))
    g.link(money_id, "PAYS", vendor_id, posted_at=datetime.utcnow())


def test_vendor_concentration_pushes_above_threshold(client):
    c, g = client
    # Two equal vendors at £100k each — ALPHA starts at 50% concentration.
    # After ~50 PO insertions averaging £20.1k, ALPHA spend grows by ~£1M
    # and concentration climbs further past 12%.
    _seed_vendor(g, vendor_id="ORG-vendor-alpha", name="Alpha Co")
    _seed_vendor(g, vendor_id="ORG-vendor-beta", name="Beta Co")
    _seed_money_pays(g, money_id="MONEY-A", amount=100_000.0, vendor_id="ORG-vendor-alpha")
    _seed_money_pays(g, money_id="MONEY-B", amount=100_000.0, vendor_id="ORG-vendor-beta")

    r = c.post(
        "/api/demo/trigger/vendor-concentration?vendor_id=ORG-vendor-alpha",
        headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vendor_id"] == "ORG-vendor-alpha"
    assert body["vendor_name"] == "Alpha Co"
    assert len(body["money_inserted"]) == 50
    assert body["before_concentration_pct"] == pytest.approx(0.5, rel=1e-3)
    assert body["after_concentration_pct"] > 0.12
    # 50 rows cycling through (15,18,20,22.5,25)k = (15+18+20+22.5+25)*10 = 1005k.
    assert body["total_added_gbp"] == pytest.approx(1_005_000.0, rel=1e-3)

    rows = g.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "WHERE o.id = 'ORG-vendor-alpha' RETURN sum(m.amount) AS s"
    )
    assert float(rows[0]["s"]) == pytest.approx(100_000.0 + 1_005_000.0, rel=1e-3)


def test_vendor_concentration_picks_largest_when_no_id(client):
    c, g = client
    _seed_vendor(g, vendor_id="ORG-vendor-small", name="Small Co")
    _seed_vendor(g, vendor_id="ORG-vendor-big", name="Big Co")
    _seed_money_pays(g, money_id="MONEY-S", amount=50_000.0, vendor_id="ORG-vendor-small")
    _seed_money_pays(g, money_id="MONEY-BIG", amount=500_000.0, vendor_id="ORG-vendor-big")

    r = c.post("/api/demo/trigger/vendor-concentration?count=5", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vendor_id"] == "ORG-vendor-big"
    assert len(body["money_inserted"]) == 5


def test_vendor_concentration_handles_missing_vendor_gracefully(client):
    c, _ = client
    r = c.post("/api/demo/trigger/vendor-concentration", headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["money_inserted"] == []
    assert body["total_added_gbp"] == 0.0
    assert "no vendor" in (body.get("message") or "").lower()


# ---------------------------------------------------------------------------
# department-attrition
# ---------------------------------------------------------------------------


def _seed_person(g: EntityGraph, *, pid: str, name: str, dept: str) -> None:
    g.upsert(EntityWrite(
        kind="Person",
        id=pid,
        attrs={
            "name": name,
            "email": f"{pid.lower()}@example.com",
            "role": "engineer",
            "market": "UK",
            "department": dept,
            "employed_from": date(2022, 1, 1),
        },
        source_workflows=(),
    ))


def test_department_attrition_marks_30pct_as_leavers(client):
    c, g = client
    for i in range(10):
        _seed_person(g, pid=f"PERSON-tech-{i:02d}", name=f"Eng {i}", dept="Tech")
    # An unrelated dept member who must NOT be touched.
    _seed_person(g, pid="PERSON-finance-1", name="CFO", dept="Finance")

    r = c.post(
        "/api/demo/trigger/department-attrition?department=Tech",
        headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["department"] == "Tech"
    assert len(body["leavers_added"]) == 3  # 30% of 10 rounded
    assert body["total_in_dept"] == 10
    assert body["attrition_pct_after"] == pytest.approx(0.3, rel=1e-3)

    rows = g.query(
        "MATCH (p:Person) WHERE p.department = 'Tech' "
        "AND p.employed_to IS NOT NULL RETURN p.id AS id, p.employed_to AS et"
    )
    assert len(rows) == 3
    cutoff = date.today() - timedelta(days=31)
    for row in rows:
        et = row["et"]
        # Kuzu returns DATE as datetime.date.
        if isinstance(et, datetime):
            et = et.date()
        assert et > cutoff
        assert et <= date.today()

    # Finance person untouched.
    fin = g.query(
        "MATCH (p:Person) WHERE p.id = 'PERSON-finance-1' "
        "RETURN p.employed_to AS et"
    )
    assert fin[0]["et"] is None


def test_department_attrition_handles_missing_department(client):
    c, _ = client
    r = c.post(
        "/api/demo/trigger/department-attrition?department=Nonexistent",
        headers=HDRS,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["leavers_added"] == []
    assert body["total_in_dept"] == 0
    assert "no Persons" in (body.get("message") or "")


def test_in_flight_invoices_cascade_records_decisions(monkeypatch):
    """When an in-flight invoice is spawned on a frozen Brand, the
    ap_clerk → controller → cfo cascade runs synchronously and records
    Decision rows so the auto-escalation is visible end-to-end without
    a real workflow runtime.
    """
    from datetime import datetime
    from pathlib import Path
    import tempfile

    from fastapi.testclient import TestClient

    from api.server.main import app
    from api.server.services import persona_responder as pr
    from api.server.services.entity_graph import EntityGraph, EntityWrite
    from api.server.state import app_state

    tmp = Path(tempfile.mkdtemp())
    g = EntityGraph(tmp / "ig.kuzu")
    monkeypatch.setattr(app_state, "entities", g)
    monkeypatch.setattr(pr, "_lazy_app_graph", lambda: g, raising=False)
    pr.PERSONA_DEFINITIONS = pr._load_personae()

    # Seed BRAND-frozen + record an active policy_set freeze on it.
    g.upsert(EntityWrite(
        kind="Brand", id="BRAND-frozen",
        attrs={"name": "Frozen", "annual_budget_gbp": 1_000_000.0,
               "budget_remaining_gbp": 0.0, "attributes": "{}"},
        source_workflows=(),
    ))
    g.record_decision(
        workflow_id="WF-FREEZE-1", phase="policy_set", persona_role="cfo",
        verdict="freeze", reason="test setup",
        decided_at=datetime.utcnow(), source_event="test",
        attributes={"expiry_days": 14, "scope": "po"},
        decided_on=("BRAND-frozen",),
    )

    client = TestClient(app)
    r = client.post(
        "/api/demo/trigger/in-flight-invoices?brand_id=BRAND-frozen&count=1",
        headers={"x-actor-role": "executive"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 1
    cascades = body.get("cascades") or []
    assert len(cascades) == 1
    decisions = cascades[0]["decisions"]
    # ap_clerk should have escalated due to the active freeze.
    assert any(
        d["role"] == "ap_clerk" and d["verdict"] == "escalate"
        for d in decisions
    ), f"expected ap_clerk to escalate; got {decisions}"

    # Decision rows should exist in the graph for the cascade.
    rows = g.query(
        "MATCH (d:Decision) WHERE d.source_event = 'demo.in_flight_invoice' "
        "RETURN d.persona_role AS who, d.verdict AS v ORDER BY who"
    )
    roles = {r["who"]: r["v"] for r in rows}
    assert "ap_clerk" in roles, f"ap_clerk decision missing; got {roles}"
    assert roles["ap_clerk"] == "escalate"
