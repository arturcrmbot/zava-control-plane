"""Tests for ``auto_block_rule_learner`` (pitch-i2).

Mirrors the FakeGraph + real EventBus pattern used by
``test_vendor_block_watcher.py``. The fake graph adds a tiny
``record_decision`` shim because the learner uses it to mint the
auto-block-rule Decision node.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from api.server.services.ambient_agents import auto_block_rule_learner
from api.server.services.ambient_agents.auto_block_rule_learner import (
    AutoBlockRuleLearner,
    is_vendor_auto_blocked,
)
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


class FakeGraph:
    """In-memory stand-in covering the surface used by the learner."""

    def __init__(self) -> None:
        self.decisions: list[dict] = []
        self._next_id = 0

    def record_decision(
        self,
        *,
        workflow_id: str,
        phase: str,
        persona_role: str,
        verdict: str,
        reason: str,
        decided_at: _dt.datetime,
        source_event: str,
        attributes: dict,
        decided_on: tuple[str, ...] = (),
    ) -> str:
        # PAT-001 dedupe: (workflow_id, phase, persona_role) is unique.
        for d in self.decisions:
            if (
                d["workflow_id"] == workflow_id
                and d["phase"] == phase
                and d["persona_role"] == persona_role
            ):
                return d["id"]
        self._next_id += 1
        did = f"DEC-AUTO-{self._next_id:04d}"
        self.decisions.append(
            {
                "id": did,
                "workflow_id": workflow_id,
                "phase": phase,
                "persona_role": persona_role,
                "verdict": verdict,
                "reason": reason,
                "decided_at": decided_at,
                "source_event": source_event,
                "attributes": json.dumps(attributes, default=str),
                "decided_on": list(decided_on),
            }
        )
        return did

    def query_one(self, cypher: str, params: dict | None = None):
        params = params or {}
        if "MATCH (d:Decision)" in cypher and "phase" in cypher:
            wf = params.get("wf")
            ph = params.get("ph")
            for d in self.decisions:
                if d["phase"] == ph and d["workflow_id"] == wf:
                    return {"id": d["id"]}
        return None


@pytest.fixture(autouse=True)
def _reset_module_state():
    auto_block_rule_learner._reset_for_tests()
    yield
    auto_block_rule_learner._reset_for_tests()


@pytest.fixture
def wired():
    bus = EventBus()
    graph = FakeGraph()
    learner = AutoBlockRuleLearner()
    learner.start(bus, graph)
    captured: list[FleetEvent] = []
    bus.on("policy.installed", lambda e: captured.append(e))
    yield bus, graph, learner, captured
    learner.stop()


def _emit_reject(bus: EventBus, vendor_id: str, decision_id: str) -> None:
    bus.emit(
        FleetEvent(
            type="decision.recorded",
            workflow_id=f"VKY-{decision_id}",
            decision_id=decision_id,
            phase="finance_signoff",
            persona_role="vendor_kyc_finance_bp",
            verdict="reject",
            decided_at="2025-01-01T00:00:00",
            vendor_id=vendor_id,
        )
    )


def test_two_rejections_do_not_install_rule(wired):
    bus, graph, learner, captured = wired
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-1")
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-2")
    assert captured == []
    assert graph.decisions == []
    assert "ORG-VENDOR-1" not in learner.installed_vendors
    assert is_vendor_auto_blocked("ORG-VENDOR-1") is False


def test_third_rejection_installs_rule_and_emits_policy_installed(wired):
    bus, graph, learner, captured = wired
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-1")
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-2")
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-3")
    assert "ORG-VENDOR-1" in learner.installed_vendors
    assert len(graph.decisions) == 1
    rule = graph.decisions[0]
    assert rule["phase"] == "auto-block-rule"
    assert rule["persona_role"] == "auto_block_rule_learner"
    assert rule["verdict"] == "block"
    assert rule["reason"] == "3 historical rejections"
    assert rule["workflow_id"] == "AUTO-BLOCK-ORG-VENDOR-1"
    assert rule["decided_on"] == ["ORG-VENDOR-1"]
    attrs = json.loads(rule["attributes"])
    assert attrs["vendor_id"] == "ORG-VENDOR-1"
    assert "installed_at" in attrs
    assert attrs["rejection_decisions"] == ["DEC-1", "DEC-2", "DEC-3"]
    assert len(captured) == 1
    payload = captured[0].model_dump()
    assert payload["policy"] == "auto-block-rule"
    assert payload["vendor_id"] == "ORG-VENDOR-1"
    assert payload["rejection_count"] == 3
    assert payload["installed_by"] == "auto_block_rule_learner"
    assert payload["decision_id"] == rule["id"]
    assert is_vendor_auto_blocked("ORG-VENDOR-1") is True


def test_fourth_rejection_is_idempotent(wired):
    bus, graph, learner, captured = wired
    for did in ("DEC-1", "DEC-2", "DEC-3", "DEC-4", "DEC-5"):
        _emit_reject(bus, "ORG-VENDOR-1", did)
    assert len(captured) == 1, "policy.installed must fire exactly once per vendor"
    assert len(graph.decisions) == 1


def test_replayed_decision_id_does_not_double_count(wired):
    bus, graph, learner, captured = wired
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-1")
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-1")  # replay
    _emit_reject(bus, "ORG-VENDOR-1", "DEC-2")
    assert captured == []
    assert "ORG-VENDOR-1" not in learner.installed_vendors


def test_two_vendors_install_independently(wired):
    bus, graph, learner, captured = wired
    for did in ("A1", "A2", "A3"):
        _emit_reject(bus, "ORG-VENDOR-A", did)
    for did in ("B1", "B2"):
        _emit_reject(bus, "ORG-VENDOR-B", did)
    assert "ORG-VENDOR-A" in learner.installed_vendors
    assert "ORG-VENDOR-B" not in learner.installed_vendors
    assert len(captured) == 1
    assert captured[0].model_dump()["vendor_id"] == "ORG-VENDOR-A"


def test_non_kyc_persona_is_ignored(wired):
    bus, graph, learner, captured = wired
    for did in ("X1", "X2", "X3"):
        bus.emit(
            FleetEvent(
                type="decision.recorded",
                workflow_id=f"VKY-{did}",
                decision_id=did,
                persona_role="cv_crystalliser",
                verdict="reject",
                vendor_id="ORG-VENDOR-1",
            )
        )
    assert captured == []
    assert "ORG-VENDOR-1" not in learner.installed_vendors


def test_approve_verdict_does_not_count(wired):
    bus, graph, learner, captured = wired
    for did, v in (("DEC-1", "reject"), ("DEC-2", "approve"), ("DEC-3", "reject")):
        bus.emit(
            FleetEvent(
                type="decision.recorded",
                workflow_id=f"VKY-{did}",
                decision_id=did,
                persona_role="vendor_kyc_finance_bp",
                verdict=v,
                vendor_id="ORG-VENDOR-1",
            )
        )
    assert captured == []
    assert "ORG-VENDOR-1" not in learner.installed_vendors


def test_malformed_event_does_not_crash_bus(wired):
    bus, graph, learner, captured = wired
    bus.emit(FleetEvent(type="decision.recorded"))
    for did in ("DEC-1", "DEC-2", "DEC-3"):
        _emit_reject(bus, "ORG-VENDOR-1", did)
    assert "ORG-VENDOR-1" in learner.installed_vendors


def test_module_level_start_stop_round_trip():
    bus = EventBus()
    graph = FakeGraph()
    auto_block_rule_learner.start(bus, graph)
    auto_block_rule_learner.stop()


def test_is_vendor_auto_blocked_falls_back_to_memory_when_no_graph():
    bus = EventBus()
    learner = AutoBlockRuleLearner()
    learner.start(bus, None)  # no graph
    try:
        for did in ("DEC-1", "DEC-2", "DEC-3"):
            _emit_reject(bus, "ORG-VENDOR-Z", did)
        assert "ORG-VENDOR-Z" in learner.installed_vendors
        assert is_vendor_auto_blocked("ORG-VENDOR-Z") is True
        assert is_vendor_auto_blocked("ORG-VENDOR-OTHER") is False
    finally:
        learner.stop()
