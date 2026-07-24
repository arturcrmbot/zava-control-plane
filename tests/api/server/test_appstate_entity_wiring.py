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
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture(autouse=True)
def _default_entity_plane(monkeypatch):
    monkeypatch.delenv("ENTITY_PLANE_ENABLED", raising=False)


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


@pytest.mark.parametrize("value", ["", "   ", None])
def test_blank_entity_plane_env_keeps_plane_enabled(tmp_path: Path, monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ENTITY_PLANE_ENABLED", raising=False)
    else:
        monkeypatch.setenv("ENTITY_PLANE_ENABLED", value)

    state_mod = _reload_state_module(monkeypatch, tmp_path)
    asyncio.run(state_mod.app_state.aclose())

    state = state_mod.AppState()
    try:
        assert state._entity_plane_enabled is True
        assert hasattr(state, "entities")
    finally:
        asyncio.run(state.aclose())
        asyncio.run(state.aclose())


def test_memory_backend_fallback_skips_mem0_import(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("MEMORY_BACKEND", "fallback")
    sys.modules.pop("api.server.services.lessons.mem0_store", None)

    import api.server.services.memory.domain_memory as domain_memory
    import api.server.services.memory.fallback_memory as fallback_memory

    sentinel = object()
    monkeypatch.setattr(
        domain_memory,
        "configured_memory_domains",
        lambda raw, allowed: ["hiring"],
    )
    monkeypatch.setattr(
        domain_memory,
        "build_domain_memories",
        lambda domains, memory: {"hiring": memory},
    )
    monkeypatch.setattr(fallback_memory, "get_fallback_memory", lambda: sentinel)

    state_mod = _reload_state_module(monkeypatch, tmp_path)
    try:
        assert state_mod.app_state.domain_memories["hiring"] is sentinel
        assert "api.server.services.lessons.mem0_store" not in sys.modules
    finally:
        asyncio.run(state_mod.app_state.aclose())


def test_lessons_package_import_does_not_load_mem0_store(monkeypatch):
    sys.modules.pop("api.server.services.lessons.mem0_store", None)
    sys.modules.pop("api.server.services.lessons", None)

    import api.server.services.lessons.cost_budget  # noqa: F401

    assert "api.server.services.lessons.mem0_store" not in sys.modules


def test_memory_backend_auto_falls_back_on_mem0_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.delenv("MEMORY_BACKEND", raising=False)

    import api.server.services.lessons.mem0_store as mem0_store
    import api.server.services.memory.domain_memory as domain_memory
    import api.server.services.memory.fallback_memory as fallback_memory

    sentinel = object()
    build_mock = Mock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(mem0_store, "build_default_memory", build_mock)
    monkeypatch.setattr(
        domain_memory,
        "configured_memory_domains",
        lambda raw, allowed: ["hiring"],
    )
    monkeypatch.setattr(
        domain_memory,
        "build_domain_memories",
        lambda domains, memory: {"hiring": memory},
    )
    monkeypatch.setattr(fallback_memory, "get_fallback_memory", lambda: sentinel)

    state_mod = _reload_state_module(monkeypatch, tmp_path)
    try:
        assert state_mod.app_state.domain_memories["hiring"] is sentinel
        assert build_mock.call_count == 1
    finally:
        asyncio.run(state_mod.app_state.aclose())


def test_memory_backend_mem0_raises_on_setup_error(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("MEMORY_BACKEND", "mem0")

    import api.server.services.lessons.mem0_store as mem0_store
    import api.server.services.memory.domain_memory as domain_memory

    build_mock = Mock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(mem0_store, "build_default_memory", build_mock)
    monkeypatch.setattr(
        domain_memory,
        "configured_memory_domains",
        lambda raw, allowed: ["hiring"],
    )
    monkeypatch.setattr(
        domain_memory,
        "build_domain_memories",
        lambda domains, memory: {"hiring": memory},
    )

    import api.server.state as state_mod
    with pytest.raises(
        RuntimeError,
        match="MEMORY_BACKEND=mem0 requires a working Mem0 backend",
    ):
        importlib.reload(state_mod)
    assert build_mock.call_count == 1


def test_memory_backend_replay_forces_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("ZAVA_MODE", "replay")
    monkeypatch.setenv("MEMORY_BACKEND", "mem0")
    sys.modules.pop("api.server.services.lessons.mem0_store", None)

    import api.server.services.lessons.mem0_store as mem0_store
    import api.server.services.memory.domain_memory as domain_memory
    import api.server.services.memory.fallback_memory as fallback_memory

    build_mock = Mock(
        side_effect=AssertionError("Mem0 should not be built in replay")
    )
    sentinel = object()
    monkeypatch.setattr(mem0_store, "build_default_memory", build_mock)
    monkeypatch.setattr(
        domain_memory,
        "configured_memory_domains",
        lambda raw, allowed: ["hiring"],
    )
    monkeypatch.setattr(
        domain_memory,
        "build_domain_memories",
        lambda domains, memory: {"hiring": memory},
    )
    monkeypatch.setattr(fallback_memory, "get_fallback_memory", lambda: sentinel)

    state_mod = _reload_state_module(monkeypatch, tmp_path)
    try:
        assert state_mod.app_state.domain_memories["hiring"] is sentinel
        assert build_mock.call_count == 0
    finally:
        asyncio.run(state_mod.app_state.aclose())


def test_memory_backend_invalid_value_fails_fast(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENTITY_PLANE_ENABLED", "0")
    monkeypatch.setenv("MEMORY_BACKEND", "sometimes")

    import api.server.state as state_mod
    with pytest.raises(ValueError, match="Invalid MEMORY_BACKEND value"):
        importlib.reload(state_mod)
