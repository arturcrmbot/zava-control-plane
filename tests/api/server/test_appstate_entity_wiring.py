"""Phase 1 sub-phase 4 — TASK-029 / TASK-029b.

AppState now constructs the entity-graph plane (EntityGraph + reflector)
in its ``__init__``. These tests pin two contracts:

* TASK-029: types are correctly wired and bootstrap fires at construction
  time (Persons land); ``aclose`` is idempotent.
* TASK-029b: bootstrap completes BEFORE the reflector subscribes — proven
  end-to-end by emitting a vendor-kyc workflow event after construction
  and observing the projected vendor Org node.
"""
from __future__ import annotations

import asyncio
import importlib
import time
from pathlib import Path

import pytest


def _reload_state_module(monkeypatch, tmp_path: Path):
    """Set PORTAL_DATA_DIR before re-importing api.server.state.

    The module reads ``PORTAL_DATA_DIR`` at import time and constructs the
    module-level ``app_state`` singleton. To get a fresh AppState pointing
    at a tmp kuzu file, we must reload the module after the env var is set.
    """
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    import api.server.state as state_mod
    importlib.reload(state_mod)
    return state_mod


def test_appstate_initialises_entity_graph_and_reflector(tmp_path: Path, monkeypatch):
    """AppState wires EntityGraph + reflector at construction."""
    state_mod = _reload_state_module(monkeypatch, tmp_path)
    from api.server.services.entity_graph import EntityGraph
    from api.server.services.entity_reflector import EntityReflector

    # Tear down the module-level singleton built at reload time so its
    # kuzu file lock doesn't collide with the AppState we construct below.
    asyncio.run(state_mod.app_state.aclose())

    state = state_mod.AppState()
    try:
        assert isinstance(state.entities, EntityGraph)
        assert isinstance(state.entity_reflector, EntityReflector)
        # Reflector is subscribed — _off is the unsubscribe callback.
        assert state.entity_reflector._off is not None

        # Bootstrap fired — at least 30 Persons from data/synthetic/employees.json
        # (TASK-008 floor).
        persons = state.entities.by_type("Person")
        assert len(persons) >= 30
    finally:
        asyncio.run(state.aclose())
        # Idempotency: second aclose must also succeed without error.
        asyncio.run(state.aclose())


def test_bootstrap_completes_before_reflector_subscribes(tmp_path: Path, monkeypatch):
    """Bootstrap MUST complete before the reflector subscribes — otherwise
    the very first workflow event after boot could race against an
    unfinished bootstrap, missing entities the projection expects."""
    state_mod = _reload_state_module(monkeypatch, tmp_path)
    from api.shared.events import FleetEvent
    from api.shared.types import Workflow

    asyncio.run(state_mod.app_state.aclose())

    state = state_mod.AppState()
    try:
        # EMP-0001 was loaded by bootstrap → already carries the
        # ``bootstrap`` source workflow tag.
        bootstrap_emp = state.entities.get("PERSON-EMP-0001")
        assert bootstrap_emp is not None
        assert "bootstrap" in bootstrap_emp.get("source_workflows", [])

        # Spawn a vendor-kyc workflow + emit an event for it. The reflector
        # will resolve the workflow via state.store, dispatch to the
        # vendor-kyc projection, and upsert the vendor Organisation.
        now = time.time()
        wf = Workflow(
            id="VKY-X",
            type="vendor-kyc",
            payload={
                "vendor_name": "Test Vendor",
                "country_of_incorporation": "GB",
                "proposing_agency": "TestAgency",
                "scenario": "clean",
            },
            current_phase="Intake",
            created_at=now,
            sla_due_at=now + 3600,
            jurisdiction="London-Zava",
            agency="TestAgency",
        )
        state.store.upsert_workflow(wf)
        state.bus.emit(FleetEvent(type="workflow.completed", workflow_id="VKY-X"))

        # The vendor-kyc projection upserts ORG-vendor-<slug(vendor_name)>.
        vendor = state.entities.get("ORG-vendor-test-vendor")
        assert vendor is not None  # reflector ran cleanly post-bootstrap
    finally:
        asyncio.run(state.aclose())
