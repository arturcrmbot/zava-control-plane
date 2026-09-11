from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from api.server.services import persona_responder
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent
from api.shared.types import Workflow


def _state(monkeypatch):
    from api.server.state import app_state

    for name, value in {
        "store": StateStore(),
        "bus": EventBus(),
        "audit": MagicMock(),
        "hub": MagicMock(),
        "orchestration_history": {},
    }.items():
        monkeypatch.setattr(app_state, name, value)
    return app_state


def test_operator_only_gate_never_auto_closes_even_with_wildcard(monkeypatch):
    state = _state(monkeypatch)
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    monkeypatch.setattr(
        persona_responder,
        "raise_orchestration_event",
        AsyncMock(return_value=True),
    )
    workflow = Workflow(
        id="AUR-GUARD-1",
        type="aurora-budget-response",
        status="awaiting_hitl",
        current_phase="Executive approval",
        created_at=time.time(),
        sla_due_at=time.time() + 3600,
        jurisdiction="London-Zava",
        agency="Zava",
        orchestration_instance_id="aurora-guard-instance",
        payload={
            "hitl_context": {
                "operator_only": True,
                "persona": "cfo",
                "external_event": "aurora_budget_response_decision",
            }
        },
    )
    state.store.upsert_workflow(workflow)
    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id=workflow.id,
        persona="cfo",
        phase="Executive approval",
        external_event="aurora_budget_response_decision",
        instance_id=workflow.orchestration_instance_id,
        context={"operator_only": True},
    )

    asyncio.run(persona_responder._handle_hitl(event))
    swept = asyncio.run(persona_responder.sweep_pending_hitl())

    persona_responder.raise_orchestration_event.assert_not_awaited()
    assert swept["swept"] == 0
    assert swept["skipped"] == 1


def test_ap_gate_uses_explicit_authority_escalation_target(monkeypatch):
    _state(monkeypatch)
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    monkeypatch.setenv("PERSONA_ESCALATION_AUTO_CASCADE", "1")
    monkeypatch.setattr(persona_responder, "_hitl_gate_for", lambda *args: None)
    monkeypatch.setattr(persona_responder, "_escalation_parent", lambda role: "wrong-parent")
    monkeypatch.setattr(
        persona_responder,
        "PERSONA_DEFINITIONS",
        {
            "ap_clerk": SimpleNamespace(
                decide=lambda _context: {
                    "decision": "escalate",
                    "reason": "controller review required",
                },
                external_event="ap_invoice_processing_decision",
                personality={},
            ),
            "controller": SimpleNamespace(
                decide=lambda _context: {
                    "decision": "escalate",
                    "reason": "CFO review required",
                },
                external_event="controller_signoff_decision",
                personality={},
            ),
            "cfo": SimpleNamespace(
                decide=lambda _context: {
                    "decision": "approve",
                    "reason": "within CFO authority",
                },
                external_event="cfo_signoff_decision",
                personality={},
            ),
        },
    )
    raised = AsyncMock(return_value=True)
    monkeypatch.setattr(persona_responder, "raise_orchestration_event", raised)

    asyncio.run(persona_responder._handle_hitl(FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="API-AUR-GUARD",
        persona="ap_clerk",
        phase="ap_clerk_signoff",
        external_event="ap_invoice_processing_decision",
        instance_id="ap-aurora-instance",
        context={
            "action": "ap_invoice_approval",
            "escalation_chain": ["controller", "cfo"],
            "invoice": {"invoice_id": "INV-AUR-1", "amount_gbp": 5000},
        },
    )))

    raised.assert_awaited_once()
    assert raised.await_args.args[2]["persona"] == "cfo"
