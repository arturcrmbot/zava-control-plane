"""pitch-h5 — TalentTransferCascade entanglement bridge."""
from __future__ import annotations

import json

import pytest

from api.server.services.ambient_agents.talent_transfer_cascade import (
    TalentTransferCascade,
)
from api.server.services.entity_graph import EntityGraph, EntityWrite
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


class _FakeAudit:
    def __init__(self) -> None:
        self.entries: list[tuple[str, dict]] = []

    def log(self, action: str, details: dict) -> None:
        self.entries.append((action, dict(details)))


def _completed_event(
    *,
    workflow_id: str = "ITT-T1",
    employee_id: str = "EMP-9999",
    from_sub: str = "Zava-UK",
    to_sub: str = "Zava-DE",
) -> FleetEvent:
    return FleetEvent(
        type="workflow.completed",
        workflow_id=workflow_id,
        workflow_type="intercompany-talent-transfer",
        payload={
            "workflow_type": "intercompany-talent-transfer",
            "transfer": {
                "employee_id": employee_id,
                "from_subsidiary": from_sub,
                "to_subsidiary": to_sub,
            },
        },
    )


def _seed_person_with_assets(graph: EntityGraph, person_id: str,
                             asset_ids: list[str], from_sub: str) -> None:
    graph.upsert(EntityWrite(
        kind="Person", id=person_id, attrs={"name": "Alice"},
        source_workflows=("ITT-T1",),
    ))
    for aid in asset_ids:
        graph.upsert(EntityWrite(
            kind="Asset", id=aid,
            attrs={"kind": "laptop", "identifier": aid,
                   "attributes": json.dumps({
                       "subsidiary_id": f"ORG-subsidiary-{from_sub.lower()}",
                   })},
            source_workflows=("ITT-T1",),
        ))
        graph.link(person_id, "OWNS", aid)


@pytest.fixture
def cascade(tmp_path):
    bus = EventBus()
    audit = _FakeAudit()
    graph = EntityGraph(tmp_path / "talent.kuzu")
    graph.attach(bus=bus, audit=audit)
    casc = TalentTransferCascade(bus=bus, audit=audit, graph=graph)
    casc.start()
    yield bus, audit, graph, casc
    casc.aclose()
    graph.close()


def test_cascade_emits_four_sub_spawned_events(cascade):
    bus, _audit, _graph, _casc = cascade
    seen: list[FleetEvent] = []
    bus.on("workflow.sub_spawned", lambda e: seen.append(e))

    bus.emit(_completed_event())

    child_types = sorted(e.model_dump().get("child_workflow_type") for e in seen)
    assert child_types == sorted([
        "it-access-request", "it-access-request",
        "employee-onboarding", "perf-review",
    ])
    parent_types = {e.model_dump().get("parent_workflow_type") for e in seen}
    assert parent_types == {"intercompany-talent-transfer"}


def test_cascade_reassigns_owns_assets_to_destination(cascade):
    bus, audit, graph, _casc = cascade
    person_id = "PERSON-EMP-9999"
    asset_ids = ["ASSET-LAPTOP-1", "ASSET-PHONE-2"]
    _seed_person_with_assets(graph, person_id, asset_ids, from_sub="zava-uk")

    linked: list[FleetEvent] = []
    bus.on("entity.linked", lambda e: linked.append(e))

    bus.emit(_completed_event())

    rows = graph.query(
        "MATCH (a:Asset) WHERE a.id IN $ids RETURN a.id AS id, a.attributes AS attrs",
        {"ids": asset_ids},
    )
    by_id = {r["id"]: json.loads(r["attrs"]) for r in rows}
    assert by_id["ASSET-LAPTOP-1"]["subsidiary_id"] == "ORG-subsidiary-zava-de"
    assert by_id["ASSET-PHONE-2"]["subsidiary_id"] == "ORG-subsidiary-zava-de"

    re_linked = [e for e in linked
                 if e.model_dump().get("src_id") == person_id
                 and e.model_dump().get("rel") == "OWNS"]
    assert len(re_linked) >= 2

    audit_entries = [d for (a, d) in audit.entries
                     if a == "entity.linked"
                     and d.get("subscriber") == "talent_transfer_cascade"]
    assert len(audit_entries) == 2


def test_cascade_is_idempotent_on_retry(cascade):
    bus, _audit, graph, _casc = cascade
    _seed_person_with_assets(graph, "PERSON-EMP-9999", ["ASSET-A"], "zava-uk")
    seen: list[FleetEvent] = []
    bus.on("workflow.sub_spawned", lambda e: seen.append(e))

    bus.emit(_completed_event())
    first = len(seen)
    bus.emit(_completed_event())  # same parent + same person => no-op
    assert len(seen) == first


def test_cascade_ignores_unrelated_workflow_types(cascade):
    bus, _audit, _graph, _casc = cascade
    seen: list[FleetEvent] = []
    bus.on("workflow.sub_spawned", lambda e: seen.append(e))

    bus.emit(FleetEvent(
        type="workflow.completed", workflow_id="OTHER-1",
        workflow_type="vendor-kyc",
        payload={"workflow_type": "vendor-kyc"},
    ))
    assert seen == []
