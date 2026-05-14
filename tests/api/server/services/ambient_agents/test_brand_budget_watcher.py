"""Tests for ``brand_budget_watcher`` (pitch-h2)."""
from __future__ import annotations

import json

import pytest

from api.server.services.ambient_agents import brand_budget_watcher
from api.server.services.ambient_agents.brand_budget_watcher import (
    BrandBudgetWatcher,
)
from api.server.services.event_bus import EventBus
from api.server.services.entity_graph import EntityWrite
from api.shared.events import FleetEvent


class FakeGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, dict]] = {"Brand": {}, "Money": {}}
        self.upserts: list[EntityWrite] = []

    def add_brand(
        self, bid: str, annual: float, remaining: float | None = None
    ) -> None:
        self.nodes["Brand"][bid] = {
            "annual_budget_gbp": annual,
            "budget_remaining_gbp": remaining if remaining is not None else annual,
        }

    def add_money(
        self,
        mid: str,
        amount: float,
        brand_id: str,
        period: str,
        amount_gbp: float | None = None,
    ) -> None:
        attrs: dict = {"brand_id": brand_id}
        if amount_gbp is not None:
            attrs["amount_gbp"] = amount_gbp
        self.nodes["Money"][mid] = {
            "amount": amount,
            "period": period,
            "attributes": json.dumps(attrs),
        }

    def query_one(self, cypher: str, params=None):
        rows = self.query(cypher, params)
        return rows[0] if rows else None

    def query(self, cypher: str, params=None):
        params = params or {}
        if "MATCH (m:Money)" in cypher:
            m = self.nodes["Money"].get(params.get("id"))
            if not m:
                return []
            return [{"a": m["attributes"], "amt": m["amount"], "p": m["period"]}]
        if "MATCH (b:Brand)" in cypher:
            b = self.nodes["Brand"].get(params.get("id"))
            if not b:
                return []
            return [
                {
                    "rem": b.get("budget_remaining_gbp"),
                    "ann": b.get("annual_budget_gbp"),
                }
            ]
        return []

    def upsert(self, entity: EntityWrite) -> None:
        self.upserts.append(entity)
        bucket = self.nodes.setdefault(entity.kind, {})
        existing = bucket.get(entity.id, {})
        existing.update(entity.attrs)
        bucket[entity.id] = existing


@pytest.fixture(autouse=True)
def _reset_module_state():
    brand_budget_watcher._reset_for_tests()
    yield
    brand_budget_watcher._reset_for_tests()


@pytest.fixture
def wired():
    bus = EventBus()
    graph = FakeGraph()
    graph.add_brand("BRD-1", annual=1000.0, remaining=1000.0)
    watcher = BrandBudgetWatcher()
    watcher.start(bus, graph)
    captured: list[FleetEvent] = []
    bus.on("workflow.exception.detected", lambda e: captured.append(e))
    yield bus, graph, watcher, captured
    watcher.stop()


def _emit_money(bus, money_id, workflow_id="WF-X"):
    bus.emit(
        FleetEvent(
            type="entity.upserted",
            workflow_id=workflow_id,
            entity_id=money_id,
            kind="Money",
        )
    )


def test_money_write_decrements_brand_budget(wired):
    bus, graph, watcher, captured = wired
    graph.add_money("MNY-1", amount=250.0, brand_id="BRD-1", period="FY25-Q1")
    _emit_money(bus, "MNY-1")
    assert graph.nodes["Brand"]["BRD-1"]["budget_remaining_gbp"] == 750.0
    assert captured == []  # not yet overspent


def test_overspend_emits_exception_once(wired):
    bus, graph, watcher, captured = wired
    graph.add_money("MNY-1", amount=1500.0, brand_id="BRD-1", period="FY25-Q1")
    _emit_money(bus, "MNY-1")
    assert len(captured) == 1
    payload = captured[0].model_dump()
    assert payload["kind"] == "budget_variance"
    assert payload["brand_id"] == "BRD-1"
    assert payload["period_id"] == "FY25-Q1"
    assert payload["overspend_gbp"] == pytest.approx(500.0)


def test_same_brand_same_quarter_dedupes(wired):
    bus, graph, watcher, captured = wired
    graph.add_money("MNY-1", amount=1500.0, brand_id="BRD-1", period="FY25-Q1")
    graph.add_money("MNY-2", amount=200.0, brand_id="BRD-1", period="FY25-Q1")
    _emit_money(bus, "MNY-1")
    _emit_money(bus, "MNY-2")
    assert len(captured) == 1, "overspend already fired this quarter"


def test_different_quarter_re_emits(wired):
    bus, graph, watcher, captured = wired
    graph.add_money("MNY-1", amount=1500.0, brand_id="BRD-1", period="FY25-Q1")
    _emit_money(bus, "MNY-1")
    assert len(captured) == 1
    # Reset Brand budget to simulate the next FY quarter rollover so the
    # second overspend has a fresh starting balance.
    graph.nodes["Brand"]["BRD-1"]["budget_remaining_gbp"] = 1000.0
    graph.add_money("MNY-2", amount=1200.0, brand_id="BRD-1", period="FY25-Q2")
    _emit_money(bus, "MNY-2")
    assert len(captured) == 2
    assert captured[1].model_dump()["period_id"] == "FY25-Q2"


def test_money_without_brand_id_is_ignored(wired):
    bus, graph, watcher, captured = wired
    graph.nodes["Money"]["MNY-X"] = {
        "amount": 100.0,
        "period": "FY25-Q1",
        "attributes": json.dumps({"vendor_id": "ORG-1"}),
    }
    _emit_money(bus, "MNY-X")
    assert graph.nodes["Brand"]["BRD-1"]["budget_remaining_gbp"] == 1000.0
    assert captured == []


def test_non_money_upsert_is_ignored(wired):
    bus, graph, watcher, captured = wired
    bus.emit(
        FleetEvent(
            type="entity.upserted",
            entity_id="ORG-1",
            kind="Organisation",
        )
    )
    assert graph.upserts == []
    assert captured == []


def test_amount_gbp_attribute_is_preferred(wired):
    bus, graph, watcher, captured = wired
    graph.add_money(
        "MNY-1",
        amount=10.0,  # raw column would say only 10
        brand_id="BRD-1",
        period="FY25-Q1",
        amount_gbp=400.0,  # but the GBP attribute carries the canonical figure
    )
    _emit_money(bus, "MNY-1")
    assert graph.nodes["Brand"]["BRD-1"]["budget_remaining_gbp"] == 600.0


def test_malformed_event_does_not_crash_bus(wired):
    bus, graph, watcher, captured = wired
    bus.emit(FleetEvent(type="entity.upserted"))  # no entity_id
    bus.emit(
        FleetEvent(type="entity.upserted", entity_id="DOES-NOT-EXIST", kind="Money")
    )
    assert graph.upserts == []
    assert captured == []


def test_module_level_start_stop_round_trip():
    bus = EventBus()
    graph = FakeGraph()
    brand_budget_watcher.start(bus, graph)
    brand_budget_watcher.stop()
