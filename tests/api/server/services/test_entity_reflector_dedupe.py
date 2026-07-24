"""Projection-result dedupe semantics for :class:`EntityReflector`."""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import api.server.services.entity_reflector as entity_reflector_module
from api.server.services.entity_graph import (
    DecisionWrite,
    EntityGraph,
    EntityWrite,
)
from api.server.services.entity_reflector import EntityReflector
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.shared.events import FleetEvent
from api.shared.types import Workflow


def _make_workflow(
    workflow_id: str,
    workflow_type: str,
    *,
    payload: dict | None = None,
    status: str = "in_progress",
) -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type=workflow_type,
        status=status,
        current_phase="Intake",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-Test",
        payload=payload or {},
    )


def test_reflector_skips_unchanged_projection_for_unrelated_events(
    tmp_path: Path,
) -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = EntityGraph(tmp_path / "g.kuzu")

    # The graph (not the reflector) emits entity.upserted, decision.recorded
    # and decision.deduped. Attach mocks here to capture those side effects.
    mock_bus = MagicMock()
    mock_audit = MagicMock()
    graph.attach(bus=mock_bus, audit=mock_audit)

    def fake_projection(_wf: Workflow):
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-T1",
                attrs={"name": "Alice"},
                source_workflows=("WF-DUP",),
            ),
            DecisionWrite(
                workflow_id="WF-DUP",
                phase="approve",
                persona_role="cfo",
                verdict="approved",
                reason="ok",
                decided_at="2026-05-09T10:00:00",
                source_event="workflow.completed",
                attributes={},
                decided_on=(),
            ),
        ]

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        projections={"test-dedupe-domain": fake_projection},
    )
    reflector.start()
    try:
        store.upsert_workflow(_make_workflow("WF-DUP", "test-dedupe-domain"))

        event_bus.emit(FleetEvent(type="agent.started", workflow_id="WF-DUP"))
        event_bus.emit(FleetEvent(type="audit.appended", workflow_id="WF-DUP"))

        emitted_types = [
            call.args[0].type for call in mock_bus.emit.call_args_list
        ]
        audit_actions = [call.args[0] for call in mock_audit.log.call_args_list]

        # One Person upsert + one materialised Workflow upsert. The unrelated
        # second FleetEvent recomputes the same projection but writes nothing.
        assert emitted_types.count("entity.upserted") == 2, (
            f"expected 2 entity.upserted (Person + Workflow), got "
            f"{emitted_types!r}"
        )
        assert emitted_types.count("decision.recorded") == 1, (
            f"expected exactly 1 decision.recorded (dedup), got "
            f"{emitted_types!r}"
        )

        assert audit_actions.count("decision.recorded") == 1, (
            f"expected 1 decision.recorded audit entry, got {audit_actions!r}"
        )
        assert audit_actions.count("decision.deduped") == 0, (
            f"expected no duplicate decision audit write, got {audit_actions!r}"
        )
        assert audit_actions.count("entity.upserted") == 2, (
            f"expected no duplicate entity audit writes, got {audit_actions!r}"
        )
    finally:
        reflector.aclose()


@pytest.mark.parametrize(
    ("update", "expected_name", "expected_status"),
    [
        ({"payload": {"name": "Bob"}}, "Bob", "in_progress"),
        ({"status": "completed"}, "Alice", "completed"),
    ],
)
def test_reflector_writes_changed_payload_or_status(
    update: dict,
    expected_name: str,
    expected_status: str,
) -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = MagicMock()

    def fake_projection(workflow: Workflow):
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-CHANGE",
                attrs={"name": workflow.payload["name"]},
                source_workflows=(workflow.id,),
            )
        ]

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        projections={"test-change-domain": fake_projection},
    )
    reflector.start()
    try:
        workflow = _make_workflow(
            "WF-CHANGE",
            "test-change-domain",
            payload={"name": "Alice"},
        )
        store.upsert_workflow(workflow)
        event = FleetEvent(type="agent.started", workflow_id=workflow.id)
        event_bus.emit(event)
        event_bus.emit(event)

        changed = workflow.model_copy(update=update)
        store.upsert_workflow(changed)
        event_bus.emit(FleetEvent(type="agent.completed", workflow_id=workflow.id))

        projected_people = [
            call.args[0]
            for call in graph.upsert.call_args_list
            if call.args[0].kind == "Person"
        ]
        assert len(projected_people) == 2
        assert projected_people[-1].attrs["name"] == expected_name
        projected_workflows = [
            call.args[0]
            for call in graph.upsert.call_args_list
            if call.args[0].kind == "Workflow"
        ]
        assert len(projected_workflows) == 2
        assert projected_workflows[-1].attrs["status"] == expected_status
    finally:
        reflector.aclose()


def test_reflector_writes_changed_decision() -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = MagicMock()

    def fake_projection(workflow: Workflow):
        decision = workflow.payload["decision"]
        return [
            DecisionWrite(
                workflow_id=workflow.id,
                phase="approve",
                persona_role="cfo",
                verdict=decision["verdict"],
                reason=decision["reason"],
                decided_at="2026-05-09T10:00:00",
                source_event="workflow.completed",
            )
        ]

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        projections={"test-decision-domain": fake_projection},
    )
    reflector.start()
    try:
        workflow = _make_workflow(
            "WF-DECISION",
            "test-decision-domain",
            payload={"decision": {"verdict": "approved", "reason": "initial"}},
        )
        store.upsert_workflow(workflow)
        event = FleetEvent(type="workflow.completed", workflow_id=workflow.id)
        event_bus.emit(event)
        event_bus.emit(event)

        changed = workflow.model_copy(
            update={
                "payload": {
                    "decision": {"verdict": "rejected", "reason": "changed"}
                }
            }
        )
        store.upsert_workflow(changed)
        event_bus.emit(event)

        assert graph.record_decision.call_count == 2
        assert graph.record_decision.call_args.args[3:5] == ("rejected", "changed")
    finally:
        reflector.aclose()


def test_reflector_retries_failed_dispatch_before_caching() -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = MagicMock()
    audit = MagicMock()
    person_attempts = 0

    def upsert(op: EntityWrite) -> None:
        nonlocal person_attempts
        if op.kind != "Person":
            return
        person_attempts += 1
        if person_attempts == 1:
            raise RuntimeError("transient Kuzu failure")

    graph.upsert.side_effect = upsert

    def fake_projection(workflow: Workflow):
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-RETRY",
                attrs={"name": "Retry"},
                source_workflows=(workflow.id,),
            )
        ]

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        audit=audit,
        projections={"test-retry-domain": fake_projection},
    )
    reflector.start()
    try:
        workflow = _make_workflow("WF-RETRY", "test-retry-domain")
        store.upsert_workflow(workflow)
        event = FleetEvent(type="agent.completed", workflow_id=workflow.id)

        event_bus.emit(event)
        event_bus.emit(event)
        event_bus.emit(event)

        assert person_attempts == 2
        failures = [
            call for call in audit.log.call_args_list
            if call.args[0] == "entity.write.failed"
        ]
        assert len(failures) == 1
    finally:
        reflector.aclose()


def test_reflector_invalidates_previous_fingerprint_after_failed_change() -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = MagicMock()
    person_attempts: list[str] = []

    def upsert(op: EntityWrite) -> None:
        if op.kind != "Person":
            return
        name = op.attrs["name"]
        person_attempts.append(name)
        if name == "changed":
            raise RuntimeError("partial changed projection")

    graph.upsert.side_effect = upsert

    def fake_projection(workflow: Workflow):
        return [
            EntityWrite(
                kind="Person",
                id="PERSON-INVALIDATE",
                attrs={"name": workflow.payload["name"]},
                source_workflows=(workflow.id,),
            )
        ]

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        projections={"test-invalidation-domain": fake_projection},
    )
    reflector.start()
    try:
        initial = _make_workflow(
            "WF-INVALIDATE",
            "test-invalidation-domain",
            payload={"name": "initial"},
        )
        store.upsert_workflow(initial)
        event = FleetEvent(type="agent.completed", workflow_id=initial.id)
        event_bus.emit(event)

        store.upsert_workflow(
            initial.model_copy(update={"payload": {"name": "changed"}})
        )
        event_bus.emit(event)

        # The failed changed projection may have partially mutated the graph.
        # Reverting must therefore replay the last successful projection.
        store.upsert_workflow(initial)
        event_bus.emit(event)

        assert person_attempts == ["initial", "changed", "initial"]
    finally:
        reflector.aclose()


def test_reflector_projection_fingerprint_cache_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        entity_reflector_module,
        "_PROJECTION_FINGERPRINT_CACHE_MAX",
        2,
    )
    event_bus = EventBus()
    store = StateStore()
    graph = MagicMock()

    def fake_projection(workflow: Workflow):
        return [
            EntityWrite(
                kind="Person",
                id=f"PERSON-{workflow.id}",
                attrs={"name": workflow.id},
                source_workflows=(workflow.id,),
            )
        ]

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        projections={"test-cache-domain": fake_projection},
    )
    reflector.start()
    try:
        for index in range(1, 4):
            workflow_id = f"WF-{index}"
            store.upsert_workflow(_make_workflow(workflow_id, "test-cache-domain"))
            event_bus.emit(FleetEvent(type="agent.started", workflow_id=workflow_id))

        assert len(reflector._projection_fingerprints) == 2

        # WF-1 was evicted, so it writes again. WF-3 remains cached and skips.
        event_bus.emit(FleetEvent(type="agent.completed", workflow_id="WF-1"))
        event_bus.emit(FleetEvent(type="agent.completed", workflow_id="WF-3"))
        assert graph.upsert.call_count == 8
        assert len(reflector._projection_fingerprints) == 2
    finally:
        reflector.aclose()


def test_reflector_still_audits_unsupported_projection_ops() -> None:
    event_bus = EventBus()
    store = StateStore()
    graph = MagicMock()
    audit = MagicMock()

    class UnsupportedOp:
        pass

    reflector = EntityReflector(
        event_bus,
        store,
        graph,
        audit=audit,
        projections={"test-unsupported-domain": lambda _workflow: [UnsupportedOp()]},
    )
    reflector.start()
    try:
        workflow = _make_workflow("WF-UNSUPPORTED", "test-unsupported-domain")
        store.upsert_workflow(workflow)
        event_bus.emit(
            FleetEvent(type="agent.completed", workflow_id=workflow.id)
        )

        failures = [
            call.args[1]
            for call in audit.log.call_args_list
            if call.args[0] == "entity.write.failed"
        ]
        assert len(failures) == 1
        assert failures[0]["kind"] == "UnsupportedOp"
    finally:
        reflector.aclose()
