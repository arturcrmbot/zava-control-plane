"""Test the perf-review projection (TASK-023)."""
from __future__ import annotations

from api.server.services.entity_graph import DecisionWrite, EntityWrite
from api.server.services.entity_projections.perf_review import (
    project, WORKFLOW_TYPE,
)

from ._helpers import fixture_payload, make_workflow


def test_perf_review_projection_emits_person_and_period():
    payload = fixture_payload("perf-review", "reviewees.json")
    wf = make_workflow("PRR-T1", WORKFLOW_TYPE, payload)

    ops = project(wf)
    entities = [o for o in ops if isinstance(o, EntityWrite)]
    kinds = {e.kind for e in entities}
    assert {"Person", "Period"} == kinds
    period = next(e for e in entities if e.kind == "Period")
    assert period.attrs["kind"] == "review-cycle"
    assert period.id == f"PERIOD-{payload['cycle']}"


def test_perf_review_projection_emits_two_decisions_when_payload_has_them():
    payload = fixture_payload("perf-review", "reviewees.json")
    wf = make_workflow(
        "PRR-T2", WORKFLOW_TYPE, payload,
        decisions=[
            {"phase": "hr_calibration", "verdict": "approve", "reason": "ok",
             "decided_at": "2026-06-01T10:00:00+00:00"},
            {"phase": "line_manager_delivery", "verdict": "delivered",
             "reason": "done", "decided_at": "2026-06-02T10:00:00+00:00"},
        ],
    )
    decisions = [o for o in project(wf) if isinstance(o, DecisionWrite)]
    assert len(decisions) == 2
