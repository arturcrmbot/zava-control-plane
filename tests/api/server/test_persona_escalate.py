"""Persona escalate verdict — gate stays open, FleetEvent emitted, FM
triage wakes on workflow.hitl.escalated.

Per TASK-041 of plan/feature-fleet-domain-substrate-1.md.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

from api.server.services import persona_responder
from api.server.services.event_bus import EventBus
from api.server.services.triage import Triage
from api.server.state import app_state
from api.shared.events import FleetEvent


@pytest.fixture(autouse=True)
def _reset_personae(monkeypatch):
    # Force reload from disk + ensure vendor_kyc_finance_bp is auto-close.
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "vendor_kyc_finance_bp")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()


def test_escalate_does_not_raise_orchestration_event(monkeypatch):
    """When a persona returns escalate, the responder must NOT call
    raise_orchestration_event — the Durable gate stays parked."""
    raised: list[tuple[str, str, dict]] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    # Use a fresh bus + capture emitted events.
    bus = EventBus()
    monkeypatch.setattr(app_state, "bus", bus)
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    # High-risk-jurisdiction context triggers vendor_kyc_finance_bp escalate.
    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="VKY-T01",
        persona="vendor_kyc_finance_bp",
        external_event="finance_signoff_decision",
        instance_id="INST-VKY-T01",
        context={
            "kyc_diligence": {"entity_sanctions_hits": [],
                              "country_of_incorporation": "RU"},
            "ubo_resolver": {"ubo_sanctions_hits": [],
                             "adverse_media_hits": []},
        },
    )
    asyncio.run(persona_responder._handle_hitl(event))

    assert raised == [], f"expected no orchestration event raised; got {raised}"
    escalated = [e for e in captured if e.type == "workflow.hitl.escalated"]
    assert escalated, f"expected workflow.hitl.escalated; saw {[e.type for e in captured]}"
    e = escalated[0]
    data = e.model_dump()
    assert data["persona"] == "vendor_kyc_finance_bp"
    assert "high-risk jurisdiction" in (data.get("reason") or "").lower()


def test_escalate_event_wakes_triage():
    t = Triage()
    e = FleetEvent(type="workflow.hitl.escalated", workflow_id="VKY-T01",
                   persona="vendor_kyc_finance_bp")
    assert t.should_wake(e), "triage should wake on workflow.hitl.escalated"


def test_approve_path_still_raises_event(monkeypatch):
    """Sanity check: a persona returning `approve` must still raise the
    orchestration event (escalate is the new path; approve/reject unchanged)."""
    raised: list[tuple[str, str, dict]] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="VKY-T02",
        persona="vendor_kyc_finance_bp",
        external_event="finance_signoff_decision",
        instance_id="INST-VKY-T02",
        context={
            "kyc_diligence": {"entity_sanctions_hits": [],
                              "country_of_incorporation": "GB"},
            "ubo_resolver": {"ubo_sanctions_hits": [], "adverse_media_hits": []},
        },
    )
    asyncio.run(persona_responder._handle_hitl(event))

    assert len(raised) == 1
    inst, event_name, payload = raised[0]
    assert inst == "INST-VKY-T02"
    assert event_name == "finance_signoff_decision"
    assert payload["decision"] == "approve"
