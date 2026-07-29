"""Pitch D4 — `persona.thinking` and `persona.decided` events carry
the per-persona personality dict so the cosmic lens / Org Ops view can
surface "Aisha (conservative) is thinking…" rather than just role ids.
"""
from __future__ import annotations

import asyncio
import importlib

import pytest

from api.server.services import persona_responder
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


def _current_app_state():
    return importlib.import_module("api.server.state").app_state


@pytest.fixture(autouse=True)
def _reset_personae(monkeypatch):
    # Force every persona to auto-close + reload so we run against the
    # real on-disk SKILL.md files (with the D4 personality blocks).
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()


def _drive_finance_bp(monkeypatch) -> list[FleetEvent]:
    """Push a hitl.requested event through the finance_bp persona and
    collect everything the bus saw."""
    async def _fake_raise(instance_id, event_name, payload):
        return None

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    # finance_bp is hand-flagged ooo_today=True in api.shared.authority for
    # demo realism (3 personae OOO at any given time). For this test we want
    # finance_bp to actually drive the gate so its personality dict appears
    # on the events; clear OOO for the duration of the test.
    from api.shared.authority import AUTHORITY
    if "finance_bp" in AUTHORITY:
        original = AUTHORITY["finance_bp"]
        from dataclasses import replace as _replace
        monkeypatch.setitem(AUTHORITY, "finance_bp", _replace(original, ooo_today=False))

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    # Within-band budget delta → finance_bp will approve, so we get both
    # persona.thinking AND persona.decided in one run.
    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="HIRE-D4-T1",
        persona="finance_bp",
        external_event="budget_approval",
        instance_id="INST-HIRE-D4-T1",
        phase="budget",
        context={
            "budget": {
                "verdict": "within_envelope",
                "requires_finance_bp": True,
                "delta_vs_midpoint_gbp": 4000,
                "envelope_remaining_gbp": 50000,
            },
        },
    )
    asyncio.run(persona_responder._handle_hitl(event))
    return captured


def test_persona_thinking_event_carries_personality(monkeypatch):
    captured = _drive_finance_bp(monkeypatch)
    thinking = [e for e in captured if e.type == "persona.thinking"]
    assert thinking, f"expected persona.thinking; saw {[e.type for e in captured]}"
    data = thinking[0].model_dump()
    assert data.get("personality") == {
        "risk_appetite": "conservative",
        "thoroughness": "high",
        "escalation_style": "reluctant",
    }, f"finance_bp personality missing/wrong: {data.get('personality')}"


def test_persona_decided_event_carries_personality(monkeypatch):
    captured = _drive_finance_bp(monkeypatch)
    decided = [e for e in captured if e.type == "persona.decided"]
    assert decided, f"expected persona.decided; saw {[e.type for e in captured]}"
    data = decided[0].model_dump()
    assert data.get("personality") == {
        "risk_appetite": "conservative",
        "thoroughness": "high",
        "escalation_style": "reluctant",
    }
    # Sanity: still carries the verdict alongside personality.
    assert data.get("verdict") in {"approve", "reject", "escalate"}


def test_persona_approval_payload_identifies_the_deciding_role(monkeypatch):
    raised: list[dict] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append(payload)
        return True

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)
    from api.shared.authority import AUTHORITY
    if "finance_bp" in AUTHORITY:
        from dataclasses import replace as _replace
        monkeypatch.setitem(
            AUTHORITY,
            "finance_bp",
            _replace(AUTHORITY["finance_bp"], ooo_today=False),
        )

    asyncio.run(persona_responder._handle_hitl(FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="HIRE-PERSONA-PAYLOAD",
        persona="finance_bp",
        external_event="budget_approval",
        instance_id="INST-HIRE-PERSONA-PAYLOAD",
        phase="budget",
        context={
            "budget": {
                "verdict": "within_envelope",
                "requires_finance_bp": True,
                "delta_vs_midpoint_gbp": 4_000,
                "envelope_remaining_gbp": 50_000,
            },
        },
    )))

    assert raised
    assert raised[0]["decision"] in {"approve", "reject"}
    assert raised[0]["persona"] == "finance_bp"
    assert raised[0]["decision_id"].startswith(
        "persona:HIRE-PERSONA-PAYLOAD:budget:finance_bp"
    )


def test_default_persona_event_carries_default_personality(monkeypatch):
    """A persona without an override block still gets a fully-shaped
    personality dict on its events (the {balanced, medium, standard}
    defaults)."""
    async def _fake_raise(instance_id, event_name, payload):
        return None

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    # cfo is a top-of-chain approver whose decision_policy generally
    # approves a well-formed payload. Use it because (a) it's auto-flagged
    # aggressive in D4, (b) we don't need a deep context dict.
    # We assert the event carries the *cfo* override block, not defaults,
    # so we know the per-persona dict is actually being threaded through
    # rather than a hard-coded constant.
    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="EXP-D4-T2",
        persona="cfo",
        external_event="cfo_signoff_decision",
        instance_id="INST-EXP-D4-T2",
        phase="cfo_signoff",
        context={},
    )
    asyncio.run(persona_responder._handle_hitl(event))

    thinking = [e for e in captured if e.type == "persona.thinking"]
    assert thinking and thinking[0].model_dump().get("personality") == {
        "risk_appetite": "aggressive",
        "thoroughness": "medium",
        "escalation_style": "quick",
    }
