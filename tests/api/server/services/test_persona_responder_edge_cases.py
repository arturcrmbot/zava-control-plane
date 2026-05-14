"""Pitch-c6: persona_responder runtime handling of long-tail HITL rolls.

Forces each new probability path (sick, holiday, override, timeout)
deterministically by stubbing ``_hitl_gate_for`` + injecting a fixed
sequence into ``random.random``. Validates:

- sick / holiday / timeout cascade to the persona's delegate (parent).
- timeout also emits ``workflow.hitl.timeout`` on the bus.
- override flips the persona's decision (approve→reject) and tags
  ``[override]`` on the reason.
- first-hit-wins ordering: sick > holiday > override > timeout.
- when all four probabilities are zero, none of the new paths fire.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest

from api.server.services import persona_responder
from api.server.services.event_bus import EventBus
from api.shared.domains import HitlGate
from api.shared.events import FleetEvent


@pytest.fixture(autouse=True)
def _reset_personae(monkeypatch):
    # vendor_kyc_finance_bp is the persona used for the override path —
    # it must be in the auto-close set so _handle_hitl actually proceeds.
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "vendor_kyc_finance_bp")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()


def _current_app_state():
    import importlib
    return importlib.import_module("api.server.state").app_state


def _seq_random(seq):
    """Return a callable that pops floats off ``seq`` in order.

    Used as a deterministic stand-in for ``random.random`` so the
    sick/holiday/override/timeout rolls fire in the order we want.
    """
    iterator = iter(seq)

    def _next():
        try:
            return next(iterator)
        except StopIteration:
            return 1.0  # any subsequent rolls miss
    return _next


def _stub_gate(monkeypatch, **probs):
    gate = HitlGate(
        "finance_signoff", "finance_signoff_decision",
        "vendor_kyc_finance_bp",
        wait_probability=0.0,
        sick_probability=probs.get("sick", 0.0),
        holiday_probability=probs.get("holiday", 0.0),
        timeout_probability=probs.get("timeout", 0.0),
        override_probability=probs.get("override", 0.0),
    )
    monkeypatch.setattr(
        persona_responder, "_hitl_gate_for",
        lambda wid, phase: gate,
    )
    return gate


def _build_event(workflow_id="VKY-T01", instance="INST-VKY-T01"):
    return FleetEvent(
        type="workflow.hitl.requested",
        workflow_id=workflow_id,
        persona="vendor_kyc_finance_bp",
        phase="finance_signoff",
        external_event="finance_signoff_decision",
        instance_id=instance,
        context={
            "kyc_diligence": {"entity_sanctions_hits": [],
                              "country_of_incorporation": "GB"},
            "ubo_resolver": {"ubo_sanctions_hits": [],
                             "adverse_media_hits": []},
        },
    )


def _record_cascades(monkeypatch):
    calls: list[dict[str, Any]] = []

    async def _fake_cascade(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(persona_responder, "_cascade_to_delegate", _fake_cascade)
    return calls


def test_sick_roll_cascades_to_delegate(monkeypatch):
    _stub_gate(monkeypatch, sick=1.0)
    monkeypatch.setattr(random, "random", _seq_random([0.0]))  # sick hits
    cascades = _record_cascades(monkeypatch)

    raised: list = []

    async def _fake_raise(*a, **kw):
        raised.append((a, kw))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert len(cascades) == 1
    assert cascades[0]["reason"] == "sick"
    assert cascades[0]["persona_role"] == "vendor_kyc_finance_bp"
    assert raised == [], "sick path must NOT raise the orchestration event"


def test_holiday_roll_cascades_to_delegate(monkeypatch):
    _stub_gate(monkeypatch, sick=0.5, holiday=1.0)
    # sick miss (roll 0.99 > 0.5), holiday hit (roll 0.0 < 1.0)
    monkeypatch.setattr(random, "random", _seq_random([0.99, 0.0]))
    cascades = _record_cascades(monkeypatch)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert len(cascades) == 1
    assert cascades[0]["reason"] == "holiday"


def test_timeout_roll_emits_event_and_cascades(monkeypatch):
    _stub_gate(monkeypatch, sick=0.5, holiday=0.5, override=0.5, timeout=1.0)
    # sick miss, holiday miss, override miss, timeout hit
    monkeypatch.setattr(random, "random", _seq_random([0.99, 0.99, 0.99, 0.0]))
    cascades = _record_cascades(monkeypatch)

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert len(cascades) == 1
    assert cascades[0]["reason"] == "timeout"
    timeout_events = [e for e in captured if e.type == "workflow.hitl.timeout"]
    assert timeout_events, (
        f"expected workflow.hitl.timeout; saw {[e.type for e in captured]}"
    )


def test_override_roll_inverts_decision(monkeypatch):
    _stub_gate(monkeypatch, sick=0.5, holiday=0.5, override=1.0)
    # sick miss, holiday miss, override hit (timeout never reached as
    # override fires first via first-hit-wins ordering — but we still
    # provide an additional roll in case the implementation rolls
    # timeout regardless).
    monkeypatch.setattr(random, "random", _seq_random([0.99, 0.99, 0.0, 0.99]))

    raised: list[tuple[str, str, dict]] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert len(raised) == 1, f"expected single raised event, got {raised}"
    _, event_name, payload = raised[0]
    assert event_name == "finance_signoff_decision"
    # vendor_kyc_finance_bp on a low-risk GB context returns "approve";
    # override flips it to "reject".
    assert payload["decision"] == "reject", (
        f"override should invert approve→reject; got {payload}"
    )
    assert "[override]" in (payload.get("reason") or "")


def test_first_hit_wins_sick_over_timeout(monkeypatch):
    _stub_gate(monkeypatch, sick=1.0, holiday=1.0, override=1.0, timeout=1.0)
    # All rolls 0.0 — every probability "hits", but sick must win.
    monkeypatch.setattr(random, "random", _seq_random([0.0, 0.0, 0.0, 0.0]))
    cascades = _record_cascades(monkeypatch)

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    raised: list = []

    async def _fake_raise(*a, **kw):
        raised.append((a, kw))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert len(cascades) == 1
    assert cascades[0]["reason"] == "sick", (
        f"first-hit-wins must pick sick first; got {cascades[0]['reason']}"
    )
    # timeout event must NOT have fired (sick won the race)
    timeouts = [e for e in captured if e.type == "workflow.hitl.timeout"]
    assert not timeouts
    assert raised == []


def test_zero_probabilities_skip_all_long_tail_paths(monkeypatch):
    _stub_gate(monkeypatch)  # all zero
    monkeypatch.setattr(random, "random", _seq_random([0.0, 0.0, 0.0, 0.0, 0.0]))
    cascades = _record_cascades(monkeypatch)

    raised: list[tuple[str, str, dict]] = []

    async def _fake_raise(instance_id, event_name, payload):
        raised.append((instance_id, event_name, payload))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert cascades == []
    # Normal happy path completes — persona decides approve, raised once.
    assert len(raised) == 1
    assert raised[0][1] == "finance_signoff_decision"


def test_missing_gate_metadata_skips_long_tail(monkeypatch):
    # _hitl_gate_for returns None → block must skip all rolls cleanly.
    monkeypatch.setattr(persona_responder, "_hitl_gate_for", lambda wid, phase: None)
    monkeypatch.setattr(random, "random", _seq_random([0.0, 0.0, 0.0, 0.0]))
    cascades = _record_cascades(monkeypatch)

    raised: list = []

    async def _fake_raise(*a, **kw):
        raised.append((a, kw))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert cascades == []
    assert len(raised) == 1  # normal happy path
