"""Decision-write behaviour for ``EntityGraph.record_decision`` (TASK-007).

PAT-001 contract:

* The natural triple ``(workflow_id, phase, persona_role)`` is the dedupe
  key — repeated calls return the SAME ULID and never overwrite the
  original row's attrs.
* On mint: emits one ``decision.recorded`` bus event + one audit entry,
  plus ``DECIDED_ON`` rels for each id in ``decided_on``.
* On dedupe hit: emits ONLY a ``decision.deduped`` audit entry (the bus
  already saw the original ``decision.recorded``).
* Per-``(workflow_id, phase)`` :class:`threading.Lock` serialises racing
  writers so the check-then-mint window is atomic.
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest import mock

import pytest

from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.shared.events import FleetEvent


# Crockford-base32 alphabet (no I, L, O, U) — mirrors the producer's
# alphabet so we can verify the minted id is a structurally valid ULID.
_ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


@pytest.fixture
def graph(tmp_path: Path) -> EntityGraph:
    return EntityGraph(tmp_path / "g.kuzu")


def _record(graph: EntityGraph, **overrides) -> str:
    """Helper with sensible defaults so tests stay focused."""
    kwargs = dict(
        workflow_id="wf-1",
        phase="triage",
        persona_role="approver",
        verdict="approve",
        reason="looks good",
        decided_at=datetime(2025, 1, 1, 12, 0, 0),
        source_event="evt-1",
        attributes={"note": "ok"},
        decided_on=(),
    )
    kwargs.update(overrides)
    return graph.record_decision(**kwargs)


def test_record_decision_mints_fresh_ulid_and_writes_row(graph: EntityGraph) -> None:
    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    decision_id = _record(
        graph,
        attributes={"score": 0.91, "channel": "auto"},
    )

    assert _ULID_PATTERN.match(decision_id), f"not a valid ULID: {decision_id!r}"

    row = graph.query_one(
        "MATCH (d:Decision) WHERE d.id = $id "
        "RETURN d.workflow_id AS wf, d.phase AS ph, d.persona_role AS pr, "
        "d.verdict AS verdict, d.reason AS reason, d.source_event AS se, "
        "d.attributes AS attrs",
        {"id": decision_id},
    )
    assert row is not None
    assert row["wf"] == "wf-1"
    assert row["ph"] == "triage"
    assert row["pr"] == "approver"
    assert row["verdict"] == "approve"
    assert row["reason"] == "looks good"
    assert row["se"] == "evt-1"
    assert json.loads(row["attrs"]) == {"score": 0.91, "channel": "auto"}

    # Exactly one bus + one audit emission for the mint.
    assert bus.emit.call_count == 1
    assert audit.log.call_count == 1

    emitted = bus.emit.call_args.args[0]
    assert isinstance(emitted, FleetEvent)
    assert emitted.type == "decision.recorded"
    assert emitted.workflow_id == "wf-1"
    assert getattr(emitted, "decision_id") == decision_id
    assert getattr(emitted, "phase") == "triage"
    assert getattr(emitted, "persona_role") == "approver"

    audit_action, audit_details = audit.log.call_args.args
    assert audit_action == "decision.recorded"
    assert audit_details["decision_id"] == decision_id
    assert audit_details["workflow_id"] == "wf-1"
    assert audit_details["verdict"] == "approve"


def test_record_decision_dedupes_on_identical_triple(graph: EntityGraph) -> None:
    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    first = _record(graph, attributes={"a": 1})
    second = _record(
        graph,
        verdict="reject",        # different verdict
        reason="changed mind",   # different reason
        attributes={"a": 999},   # different attrs — must NOT overwrite
    )

    assert second == first, "dedupe must return the same ULID"

    # First-writer-wins: the original row is unchanged.
    row = graph.query_one(
        "MATCH (d:Decision) WHERE d.id = $id "
        "RETURN d.verdict AS verdict, d.reason AS reason, d.attributes AS attrs",
        {"id": first},
    )
    assert row is not None
    assert row["verdict"] == "approve"
    assert row["reason"] == "looks good"
    assert json.loads(row["attrs"]) == {"a": 1}

    # Exactly one Decision row in the graph (no duplicate mint).
    count_row = graph.query_one("MATCH (d:Decision) RETURN count(d) AS n")
    assert count_row is not None and count_row["n"] == 1

    # Bus saw the original mint exactly once; the dedupe was bus-silent.
    assert bus.emit.call_count == 1

    # Audit saw one .recorded then one .deduped.
    assert audit.log.call_count == 2
    actions = [call.args[0] for call in audit.log.call_args_list]
    assert actions == ["decision.recorded", "decision.deduped"]
    deduped_details = audit.log.call_args_list[1].args[1]
    assert deduped_details["decision_id"] == first
    assert deduped_details["workflow_id"] == "wf-1"
    assert deduped_details["phase"] == "triage"
    assert deduped_details["persona_role"] == "approver"


def test_distinct_persona_role_mints_distinct_decision(graph: EntityGraph) -> None:
    """The dedupe key is the natural triple, not just (wf, phase)."""
    a = _record(graph, persona_role="approver")
    b = _record(graph, persona_role="reviewer")

    assert a != b

    count_row = graph.query_one("MATCH (d:Decision) RETURN count(d) AS n")
    assert count_row is not None and count_row["n"] == 2


def test_decided_on_materialises_rels(graph: EntityGraph) -> None:
    graph.upsert(
        EntityWrite(
            kind="Person",
            id="PERSON-EMP-0042",
            attrs={"name": "Alice"},
        )
    )

    decision_id = _record(graph, decided_on=("PERSON-EMP-0042",))

    neighbours = graph.linked(decision_id, "decided_on")
    assert len(neighbours) == 1
    assert neighbours[0]["node"]["id"] == "PERSON-EMP-0042"
    assert neighbours[0]["rel"] == "DECIDED_ON"


def test_concurrent_callers_dedupe_on_same_triple(tmp_path: Path) -> None:
    """Two threads racing on the same (wf, phase, persona_role) must both
    return the same ULID — the per-(wf, phase) lock serialises the
    check-then-mint window."""
    graph = EntityGraph(tmp_path / "g.kuzu")
    bus = mock.Mock()
    audit = mock.Mock()
    graph.attach(bus=bus, audit=audit)

    def call() -> str:
        return graph.record_decision(
            workflow_id="wf-race",
            phase="triage",
            persona_role="approver",
            verdict="approve",
            reason="r",
            decided_at=datetime(2025, 1, 1, 12, 0, 0),
            source_event="evt-race",
            attributes={},
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = [ex.submit(call), ex.submit(call)]
        results = [f.result() for f in futures]

    assert results[0] == results[1], "racing callers diverged on ULID"

    count_row = graph.query_one("MATCH (d:Decision) RETURN count(d) AS n")
    assert count_row is not None and count_row["n"] == 1

    # Bus emitted exactly one decision.recorded.
    assert bus.emit.call_count == 1
    assert bus.emit.call_args.args[0].type == "decision.recorded"

    # Audit saw one .recorded + one .deduped.
    actions = sorted(call.args[0] for call in audit.log.call_args_list)
    assert actions == ["decision.deduped", "decision.recorded"]


def test_record_decision_without_attach_writes_silently(graph: EntityGraph) -> None:
    """Mirrors the upsert/link no-attach contract: pure write, no
    downstream emissions, no exceptions."""
    assert graph.bus is None
    assert graph.audit is None

    decision_id = _record(graph)

    row = graph.query_one(
        "MATCH (d:Decision) WHERE d.id = $id RETURN d.verdict AS verdict",
        {"id": decision_id},
    )
    assert row is not None
    assert row["verdict"] == "approve"
