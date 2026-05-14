"""Tests for ``vendor_block_watcher`` (pitch-h1).

Uses a fake graph + the real :class:`EventBus` so we can verify the
end-to-end subscribe / decision-handling / paused-emit story without
standing up KuzuDB.
"""
from __future__ import annotations

import json

import pytest

from api.server.services.ambient_agents import vendor_block_watcher
from api.server.services.ambient_agents.vendor_block_watcher import (
    VendorBlockWatcher,
)
from api.server.services.event_bus import EventBus
from api.server.services.entity_graph import EntityWrite
from api.shared.events import FleetEvent


class FakeGraph:
    """In-memory stand-in for :class:`EntityGraph` covering the surface
    used by the watcher (``query_one`` / ``query`` / ``upsert``)."""

    def __init__(self) -> None:
        # kind -> id -> attrs (mirrors columns we care about).
        self.nodes: dict[str, dict[str, dict]] = {
            "Workflow": {},
            "Organisation": {},
            "Money": {},
        }
        self.upserts: list[EntityWrite] = []

    def add_workflow(self, wid: str, workflow_type: str) -> None:
        self.nodes["Workflow"][wid] = {"workflow_type": workflow_type}

    def add_vendor(self, vid: str, attributes: dict | None = None) -> None:
        self.nodes["Organisation"][vid] = {
            "kind": "vendor",
            "attributes": json.dumps(attributes or {}),
        }

    def add_invoice(
        self, mid: str, vendor_id: str, source_workflows: tuple[str, ...]
    ) -> None:
        self.nodes["Money"][mid] = {
            "kind": "invoice",
            "attributes": json.dumps({"vendor_id": vendor_id}),
            "source_workflows": list(source_workflows),
        }

    # -- minimal Cypher dispatcher -------------------------------------

    def query_one(self, cypher: str, params: dict | None = None):
        rows = self.query(cypher, params)
        return rows[0] if rows else None

    def query(self, cypher: str, params: dict | None = None):
        params = params or {}
        if "MATCH (w:Workflow)" in cypher:
            wf = self.nodes["Workflow"].get(params.get("id"))
            return [{"t": wf["workflow_type"]}] if wf else []
        if "MATCH (o:Organisation)" in cypher and "RETURN o.attributes" in cypher:
            org = self.nodes["Organisation"].get(params.get("id"))
            return [{"a": org["attributes"]}] if org else []
        if "MATCH (m:Money)" in cypher and "CONTAINS" in cypher:
            vid = params.get("vid")
            out = []
            for mid, attrs in self.nodes["Money"].items():
                if attrs.get("kind") == "invoice" and vid in attrs.get("attributes", ""):
                    out.append({"id": mid, "sw": list(attrs.get("source_workflows", []))})
            return out
        return []

    def upsert(self, entity: EntityWrite) -> None:
        self.upserts.append(entity)
        bucket = self.nodes.setdefault(entity.kind, {})
        existing = bucket.get(entity.id, {})
        existing.update(entity.attrs)
        bucket[entity.id] = existing


@pytest.fixture(autouse=True)
def _reset_module_state():
    vendor_block_watcher._reset_for_tests()
    yield
    vendor_block_watcher._reset_for_tests()


@pytest.fixture
def wired():
    bus = EventBus()
    graph = FakeGraph()
    graph.add_workflow("VKY-0001", "vendor-kyc")
    graph.add_vendor("ORG-VENDOR-1", {"name": "Acme"})
    graph.add_invoice("MNY-INV-1", "ORG-VENDOR-1", ("API-0001",))
    graph.add_invoice("MNY-INV-2", "ORG-VENDOR-1", ("API-0002",))
    watcher = VendorBlockWatcher()
    watcher.start(bus, graph)
    captured: list[FleetEvent] = []
    bus.on("workflow.paused", lambda e: captured.append(e))
    yield bus, graph, watcher, captured
    watcher.stop()


def _vendor_attrs(graph: FakeGraph, vid: str) -> dict:
    raw = graph.nodes["Organisation"][vid]["attributes"]
    return json.loads(raw) if raw else {}


def test_red_kyc_flips_is_blocked_and_pauses_invoices(wired):
    bus, graph, watcher, captured = wired
    bus.emit(
        FleetEvent(
            type="decision.recorded",
            workflow_id="VKY-0001",
            decision_id="DEC-1",
            phase="finance_signoff",
            persona_role="vendor_kyc_finance_bp",
            verdict="reject",
            decided_at="2025-01-01T00:00:00",
            vendor_id="ORG-VENDOR-1",
        )
    )
    assert _vendor_attrs(graph, "ORG-VENDOR-1")["is_blocked"] is True
    assert "ORG-VENDOR-1" in watcher.blocked_vendors
    paused_workflow_ids = {e.model_dump().get("workflow_id") for e in captured}
    assert paused_workflow_ids == {"API-0001", "API-0002"}
    for ev in captured:
        d = ev.model_dump()
        assert d["paused_by"] == "vendor_block_watcher"
        assert d["reason"] == "vendor blocked"
        assert d["vendor_id"] == "ORG-VENDOR-1"


def test_green_reverify_clears_block(wired):
    bus, graph, watcher, captured = wired
    bus.emit(
        FleetEvent(
            type="decision.recorded",
            workflow_id="VKY-0001",
            decision_id="DEC-1",
            persona_role="vendor_kyc_finance_bp",
            verdict="reject",
            vendor_id="ORG-VENDOR-1",
        )
    )
    assert _vendor_attrs(graph, "ORG-VENDOR-1")["is_blocked"] is True
    bus.emit(
        FleetEvent(
            type="decision.recorded",
            workflow_id="VKY-0002",
            decision_id="DEC-2",
            persona_role="vendor_kyc_finance_bp",
            verdict="approve",
            vendor_id="ORG-VENDOR-1",
            workflow_type="vendor-kyc",
        )
    )
    assert _vendor_attrs(graph, "ORG-VENDOR-1")["is_blocked"] is False
    assert "ORG-VENDOR-1" not in watcher.blocked_vendors


def test_double_red_is_idempotent_and_does_not_double_emit(wired):
    bus, graph, watcher, captured = wired
    payload = dict(
        type="decision.recorded",
        workflow_id="VKY-0001",
        decision_id="DEC-1",
        persona_role="vendor_kyc_finance_bp",
        verdict="reject",
        vendor_id="ORG-VENDOR-1",
    )
    bus.emit(FleetEvent(**payload))
    first_count = len(captured)
    bus.emit(FleetEvent(**payload))
    assert len(captured) == first_count, "second red must not re-emit pauses"


def test_non_kyc_persona_is_ignored(wired):
    bus, graph, watcher, captured = wired
    bus.emit(
        FleetEvent(
            type="decision.recorded",
            workflow_id="VKY-0001",
            decision_id="DEC-1",
            persona_role="cv_crystalliser",  # not a KYC persona
            verdict="reject",
            vendor_id="ORG-VENDOR-1",
        )
    )
    assert captured == []
    assert "ORG-VENDOR-1" not in watcher.blocked_vendors


def test_malformed_event_does_not_crash_bus(wired):
    bus, graph, watcher, captured = wired
    # Emit something missing every field — handler must swallow.
    bus.emit(FleetEvent(type="decision.recorded"))
    # Following good event still processes cleanly.
    bus.emit(
        FleetEvent(
            type="decision.recorded",
            workflow_id="VKY-0001",
            decision_id="DEC-1",
            persona_role="vendor_kyc_finance_bp",
            verdict="reject",
            vendor_id="ORG-VENDOR-1",
        )
    )
    assert "ORG-VENDOR-1" in watcher.blocked_vendors


def test_module_level_start_stop_round_trip():
    """The lifespan-facing ``start`` / ``stop`` helpers must not raise."""
    bus = EventBus()
    graph = FakeGraph()
    vendor_block_watcher.start(bus, graph)
    vendor_block_watcher.stop()
