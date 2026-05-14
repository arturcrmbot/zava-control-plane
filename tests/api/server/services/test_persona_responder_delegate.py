"""Pitch-h3: persona_responder routes person-availability cascades to
the explicit ``AUTHORITY.delegate_to`` (not just the hierarchy parent),
and the d2 ``AUTHORITY.ooo_today`` flag deterministically forces the
cascade ahead of any probabilistic roll. Whenever the cascade fires for
an availability reason (ooo / sick / holiday) a ``persona.delegated``
FleetEvent is emitted so the cosmic lens can render the hand-off.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

import pytest

from api.server.services import persona_responder
from api.server.services.event_bus import EventBus
from api.shared import authority as authority_mod
from api.shared.authority import AuthorityRow
from api.shared.domains import HitlGate
from api.shared.events import FleetEvent


PERSONA = "vendor_kyc_finance_bp"


@pytest.fixture(autouse=True)
def _reset_personae(monkeypatch):
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()


def _current_app_state():
    import importlib
    return importlib.import_module("api.server.state").app_state


def _build_event(workflow_id="VKY-T01", instance="INST-VKY-T01"):
    return FleetEvent(
        type="workflow.hitl.requested",
        workflow_id=workflow_id,
        persona=PERSONA,
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


def _stub_gate(monkeypatch, **probs):
    gate = HitlGate(
        "finance_signoff", "finance_signoff_decision",
        PERSONA,
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


def _set_authority(monkeypatch, *, delegate_to: str | None, ooo_today: bool):
    """Override AUTHORITY[PERSONA] for the duration of one test."""
    new_table = dict(authority_mod.AUTHORITY)
    base = new_table.get(PERSONA)
    new_table[PERSONA] = AuthorityRow(
        role=PERSONA,
        spend_limit_gbp=base.spend_limit_gbp if base else 0.0,
        approval_actions=base.approval_actions if base else (),
        delegate_to=delegate_to,
        ooo_today=ooo_today,
    )
    monkeypatch.setattr(authority_mod, "AUTHORITY", new_table)


def _capture_bus(monkeypatch):
    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))
    return captured


def test_ooo_today_forces_cascade_to_explicit_delegate(monkeypatch):
    """AUTHORITY.ooo_today=True → unconditional cascade to delegate_to.

    No probabilistic rolls happen; the rest of the c6 long-tail logic is
    bypassed. The cascade target MUST be the explicit delegate, and a
    ``persona.delegated`` FleetEvent MUST be emitted.
    """
    _set_authority(monkeypatch, delegate_to="contract_finance_bp", ooo_today=True)
    _stub_gate(monkeypatch)  # all probs zero — proves no roll is needed
    # If the implementation accidentally rolls dice we still want a
    # deterministic 1.0 (= guaranteed miss) so any leak fails loud.
    monkeypatch.setattr(random, "random", lambda: 1.0)

    captured: list[dict[str, Any]] = []

    async def _fake_cascade(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr(persona_responder, "_cascade_to_delegate", _fake_cascade)

    raised: list = []

    async def _fake_raise(*a, **kw):
        raised.append((a, kw))

    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(persona_responder._handle_hitl(_build_event()))

    assert len(captured) == 1, f"expected one cascade, got {captured}"
    assert captured[0]["reason"] == "ooo"
    assert captured[0]["persona_role"] == PERSONA
    assert raised == [], "OOO must short-circuit before raise_orchestration_event"


def test_sick_cascade_targets_authority_delegate_and_emits_event(monkeypatch):
    """A sick roll cascades to the AUTHORITY.delegate_to target (not the
    function-hierarchy parent) AND emits ``persona.delegated``."""
    _set_authority(monkeypatch, delegate_to="contract_finance_bp", ooo_today=False)
    _stub_gate(monkeypatch, sick=1.0)
    monkeypatch.setattr(random, "random", lambda: 0.0)  # sick hits first

    # Spy on _handle_hitl recursion to capture the cascaded persona role.
    real_handle = persona_responder._handle_hitl
    cascade_personas: list[str | None] = []

    async def _spy_handle(event):
        # Record only NESTED invocations (cascade_depth > 0).
        if event.model_dump().get("_cascade_depth"):
            cascade_personas.append(event.model_dump().get("persona"))
        # Don't actually recurse — just consume the cascade.
        if event.model_dump().get("_cascade_depth"):
            return
        await real_handle(event)

    monkeypatch.setattr(persona_responder, "_handle_hitl", _spy_handle)

    captured = _capture_bus(monkeypatch)

    async def _fake_raise(*a, **kw):
        pass
    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(_spy_handle(_build_event()))

    assert cascade_personas == ["contract_finance_bp"], (
        f"sick cascade must target the authority delegate; got {cascade_personas}"
    )
    delegated = [e for e in captured if e.type == "persona.delegated"]
    assert len(delegated) == 1, (
        f"expected one persona.delegated event; got {[e.type for e in captured]}"
    )
    payload = delegated[0].model_dump()
    assert payload["from_role"] == PERSONA
    assert payload["to_role"] == "contract_finance_bp"
    assert payload["reason"] == "sick"


def test_no_delegate_to_falls_back_to_hierarchy_parent(monkeypatch):
    """delegate_to=None → cascade target is the persona-hierarchy parent
    (legacy c6 behaviour). Uses ``ap_clerk`` because it has a real
    hierarchy parent (``bp_pod_lead``); ``vendor_kyc_finance_bp`` sits
    at the top of its tree so it would mask the fallback path.
    """
    fallback_persona = "ap_clerk"
    parent = persona_responder._escalation_parent(fallback_persona)
    assert parent, (
        f"test setup error: {fallback_persona} has no hierarchy parent"
    )

    new_table = dict(authority_mod.AUTHORITY)
    base = new_table.get(fallback_persona)
    new_table[fallback_persona] = AuthorityRow(
        role=fallback_persona,
        spend_limit_gbp=base.spend_limit_gbp if base else 0.0,
        approval_actions=base.approval_actions if base else (),
        delegate_to=None,
        ooo_today=False,
    )
    monkeypatch.setattr(authority_mod, "AUTHORITY", new_table)

    gate = HitlGate(
        "ap_invoice_review", "ap_invoice_decision",
        fallback_persona,
        wait_probability=0.0,
        sick_probability=1.0,
    )
    monkeypatch.setattr(
        persona_responder, "_hitl_gate_for",
        lambda wid, phase: gate,
    )
    monkeypatch.setattr(random, "random", lambda: 0.0)

    real_handle = persona_responder._handle_hitl
    cascade_personas: list[str | None] = []

    async def _spy_handle(event):
        if event.model_dump().get("_cascade_depth"):
            cascade_personas.append(event.model_dump().get("persona"))
            return
        await real_handle(event)

    monkeypatch.setattr(persona_responder, "_handle_hitl", _spy_handle)

    _capture_bus(monkeypatch)

    async def _fake_raise(*a, **kw):
        pass
    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="AP-T01",
        persona=fallback_persona,
        phase="ap_invoice_review",
        external_event="ap_invoice_decision",
        instance_id="INST-AP-T01",
        context={},
    )
    asyncio.run(_spy_handle(event))

    assert cascade_personas == [parent], (
        f"with delegate_to=None, cascade must fall through to parent "
        f"({parent!r}); got {cascade_personas}"
    )


def test_timeout_cascade_does_not_emit_persona_delegated(monkeypatch):
    """Timeout is not a person-availability event — no persona.delegated."""
    _set_authority(monkeypatch, delegate_to="contract_finance_bp", ooo_today=False)
    _stub_gate(monkeypatch, timeout=1.0)
    # sick miss, holiday miss, override miss, timeout hit
    seq = iter([0.99, 0.99, 0.99, 0.0])
    monkeypatch.setattr(random, "random", lambda: next(seq, 1.0))

    real_handle = persona_responder._handle_hitl

    async def _spy_handle(event):
        if event.model_dump().get("_cascade_depth"):
            return
        await real_handle(event)

    monkeypatch.setattr(persona_responder, "_handle_hitl", _spy_handle)

    captured = _capture_bus(monkeypatch)

    async def _fake_raise(*a, **kw):
        pass
    monkeypatch.setattr(persona_responder, "raise_orchestration_event", _fake_raise)

    asyncio.run(_spy_handle(_build_event()))

    delegated = [e for e in captured if e.type == "persona.delegated"]
    assert delegated == [], (
        f"timeout cascade must NOT emit persona.delegated; got "
        f"{[e.model_dump() for e in delegated]}"
    )
