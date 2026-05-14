"""Pitch-j3: persona_responder records per-domain decision latency.

Drives ``_handle_hitl`` end-to-end with a stubbed durable_client and a
seeded workflow row in the in-process store, then asserts that the new
``decision_latency_seconds`` sample landed in the durable kpi_history
ring under the workflow's ``workflow_type`` as ``dim``.
"""
from __future__ import annotations

import asyncio
import importlib
import time
from pathlib import Path

import pytest

from api.server.services import kpi_history, persona_responder
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent
from api.shared.types import Workflow


def _current_app_state():
    return importlib.import_module("api.server.state").app_state


@pytest.fixture
def isolated_db(tmp_path: Path):
    db = tmp_path / "kh.sqlite"
    kpi_history.set_db_path(db)
    kpi_history.init()
    yield db
    kpi_history.set_db_path(kpi_history._DEFAULT_DB_PATH)


@pytest.fixture(autouse=True)
def _reset_personae(monkeypatch):
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "*")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()


def _seed_workflow(workflow_id: str, wf_type: str, *, age_seconds: float) -> None:
    """Drop a Workflow row into the in-process store with a back-dated
    ``created_at`` so the latency we record is non-trivial."""
    state = _current_app_state()
    now = time.time()
    wf = Workflow(
        id=workflow_id,
        type=wf_type,
        status="awaiting_hitl",
        current_phase="budget",
        created_at=now - age_seconds,
        sla_due_at=now + 86400.0,
        payload={},
        jurisdiction="UK",
        agency="zava",
    )
    state.store.upsert_workflow(wf)


def test_decision_latency_sample_recorded_after_handle_hitl(
    isolated_db, monkeypatch
):
    async def _fake_raise(instance_id, event_name, payload):
        return None

    monkeypatch.setattr(
        persona_responder, "raise_orchestration_event", _fake_raise
    )

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)

    workflow_id = "HIRE-J3-T1"
    _seed_workflow(workflow_id, "hiring", age_seconds=42.0)

    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id=workflow_id,
        persona="finance_bp",
        external_event="budget_approval",
        instance_id="INST-J3-T1",
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

    sample = kpi_history.latest("decision_latency_seconds", dim="hiring")
    assert sample is not None, "expected decision_latency_seconds sample"
    _ts, latency = sample
    assert latency >= 42.0
    assert latency < 120.0  # sanity bound — wall clock + a generous slack


def test_decision_latency_namespaced_per_domain(isolated_db, monkeypatch):
    async def _fake_raise(instance_id, event_name, payload):
        return None

    monkeypatch.setattr(
        persona_responder, "raise_orchestration_event", _fake_raise
    )

    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)

    _seed_workflow("HIRE-J3-A", "hiring", age_seconds=10.0)
    _seed_workflow("HIRE-J3-B", "hiring", age_seconds=20.0)

    for wid in ("HIRE-J3-A", "HIRE-J3-B"):
        event = FleetEvent(
            type="workflow.hitl.requested",
            workflow_id=wid,
            persona="finance_bp",
            external_event="budget_approval",
            instance_id=f"INST-{wid}",
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

    hiring_pts = kpi_history.series(
        "decision_latency_seconds", since_seconds=3600, dim="hiring"
    )
    assert len(hiring_pts) == 2
    # Cross-domain isolation: querying a different dim returns nothing.
    other = kpi_history.series(
        "decision_latency_seconds", since_seconds=3600, dim="expense-claim"
    )
    assert other == []


def test_decision_latency_silent_when_workflow_missing(
    isolated_db, monkeypatch
):
    """No workflow row → no row recorded, no exception escapes."""
    async def _fake_raise(instance_id, event_name, payload):
        return None

    monkeypatch.setattr(
        persona_responder, "raise_orchestration_event", _fake_raise
    )
    bus = EventBus()
    monkeypatch.setattr(_current_app_state(), "bus", bus)

    event = FleetEvent(
        type="workflow.hitl.requested",
        workflow_id="HIRE-J3-MISSING",
        persona="finance_bp",
        external_event="budget_approval",
        instance_id="INST-J3-MISSING",
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
    # Must not raise.
    asyncio.run(persona_responder._handle_hitl(event))
    # And nothing was recorded for any plausible dim.
    assert kpi_history.latest("decision_latency_seconds", dim="hiring") is None
