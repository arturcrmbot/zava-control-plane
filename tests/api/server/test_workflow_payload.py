"""Workflow.payload round-trip + store visibility for fleet domains.

Per TASK-013 of plan/feature-fleet-domain-substrate-1.md.
"""
from __future__ import annotations

import json

import pytest

from api.server.services.state_store import StateStore
from api.server.services.synthetic_data import (
    build_fleet_vendor_kyc_workflow,
    build_fleet_travel_preapproval_workflow,
)


def test_payload_round_trips_through_pydantic():
    w = build_fleet_vendor_kyc_workflow(
        "VKY-0001",
        record={
            "vendor_name": "Acme Holdings", "country_of_incorporation": "GB",
            "proposing_agency": "Mindshare", "scenario": "clean",
        },
    )
    dumped = w.model_dump(by_alias=True)
    assert dumped["type"] == "vendor-kyc"
    assert dumped["payload"]["vendor"]["name"] == "Acme Holdings"
    assert dumped["payload"]["scenario"] == "clean"
    # Back-compat fields are None for fleet workflows.
    assert dumped["claim"] is None
    assert dumped["invoice"] is None


def test_fleet_workflow_visible_in_store():
    store = StateStore()
    w = build_fleet_travel_preapproval_workflow(
        "TRV-0001",
        record={"employee_id": "EMP-0001", "scenario": "in-policy"},
    )
    store.upsert_workflow(w)
    items = store.list_workflows()
    assert any(it.id == "TRV-0001" and it.type == "travel-preapproval" for it in items)


def test_fleet_workflow_listed_by_phase_aggregation():
    """Mimic what query_fleet does: list workflows + aggregate by phase
    + by status. Asserts a fleet workflow is counted."""
    store = StateStore()
    store.upsert_workflow(build_fleet_vendor_kyc_workflow("VKY-A"))
    store.upsert_workflow(build_fleet_travel_preapproval_workflow("TRV-A"))
    items = store.list_workflows()
    by_phase: dict[str, int] = {}
    for it in items:
        by_phase[it.current_phase] = by_phase.get(it.current_phase, 0) + 1
    assert by_phase.get("Vendor Intake") == 1
    assert by_phase.get("Employee Lookup") == 1
