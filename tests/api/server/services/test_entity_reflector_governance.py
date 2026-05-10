"""Governance kill-switch test for :class:`EntityReflector` (TASK-013).

Registering an operator kill on
``actor=reflector.entity_reflector, tool=entity.write`` must cause
the reflector to:

* deny the dispatch (no graph writes),
* emit an ``entity.write.killed`` audit entry.

Uses the live :func:`kernel` singleton so we exercise the
``kill_switch_store → kernel → reflector`` path end-to-end.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.services.entity_projections import PROJECTIONS
from api.server.services.entity_reflector import EntityReflector
from api.server.services.event_bus import EventBus
from api.server.services.governance.kernel import kernel
from api.server.services.governance.kill_switch import kill_switch_store
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent
from api.shared.types import Workflow


def _make_workflow(workflow_id: str, workflow_type: str) -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type=workflow_type,
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-Test",
    )


@pytest.fixture
def _clean_kill_switch(monkeypatch: pytest.MonkeyPatch):
    # Kernel runs in log_only mode unless AGT_ENFORCE is set; the kill
    # switch still flips Decision.allowed=False either way.
    monkeypatch.delenv("AGT_ENFORCE", raising=False)
    kill_switch_store.clear_for_tests()
    try:
        yield
    finally:
        kill_switch_store.clear_for_tests()


def test_reflector_honours_kill_switch_via_kernel(
    tmp_path: Path, _clean_kill_switch: None
) -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = EntityGraph(tmp_path / "g.kuzu")
    audit = MagicMock()

    def fake_projection(_wf: Workflow):
        # Would upsert a Person if it ever ran.
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-KILL",
                attrs={"name": "Should Not Land"},
                source_workflows=("WF-KILL",),
            )
        ]

    PROJECTIONS["test-kill-domain"] = fake_projection

    # Register the operator kill BEFORE constructing the reflector so
    # the very first emit hits a deny.
    kill_switch_store.add(
        actor="reflector.entity_reflector",
        tool="entity.write",
        ttl_seconds=60.0,
        reason="test: pause reflector",
    )

    reflector = EntityReflector(
        event_bus, store, graph, governance=kernel(), audit=audit
    )
    reflector.start()
    try:
        store.upsert_workflow(_make_workflow("WF-KILL", "test-kill-domain"))
        event_bus.emit(FleetEvent(type="workflow.completed", workflow_id="WF-KILL"))

        # Projection never ran → graph stays empty.
        assert graph.get("PERSON-KILL") is None

        # Reflector logged the kill.
        actions = [call.args[0] for call in audit.log.call_args_list]
        assert "entity.write.killed" in actions, (
            f"expected entity.write.killed audit entry, got {actions!r}"
        )
    finally:
        reflector.aclose()
        del PROJECTIONS["test-kill-domain"]
