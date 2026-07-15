"""Tests for the registered-domain Workflow factory.

``build_registered_workflow`` is the shared factory the simulator strategic
spawners and the actor-world :class:`WorldWorkflowAdapter` both use to mint a
canonical :class:`~api.shared.types.Workflow` from registered domain metadata.
Its defining property: the initial ``current_phase`` derives from
``DOMAINS[workflow_type].phases[0]`` — never a hardcoded ``"Intake"``.
"""
from __future__ import annotations

from api.server.services.synthetic_data import build_registered_workflow
from api.shared import domains as _domains


def test_initial_phase_derives_from_registered_domain_phase_zero():
    # network-incident's first phase is "Telemetry Correlation", NOT Intake.
    w = build_registered_workflow(
        "NI-1", "network-incident", "incident",
        {"incident_site": {"id": "SITE-01"}},
    )
    assert w.type == "network-incident"
    assert w.current_phase == "Telemetry Correlation"
    assert _domains.DOMAINS["network-incident"].phases[0].name == "Telemetry Correlation"


def test_initial_phase_for_another_non_intake_domain():
    # hire-to-productive's first phase is "Joiner Intake".
    w = build_registered_workflow(
        "H2P-1", "hire-to-productive", "joiner", {"joiner_id": "EMP-1"},
    )
    assert w.current_phase == _domains.DOMAINS["hire-to-productive"].phases[0].name
    assert w.current_phase != "Intake"


def test_unregistered_type_falls_back_to_intake():
    w = build_registered_workflow("X-1", "not-a-real-domain", "thing", {"a": 1})
    assert w.current_phase == "Intake"


def test_payload_shape_matches_strategic_factory():
    # Payload nests the business object under the domain key and hoists
    # scenario to the top level (the shape the simulator + projections expect).
    observation = {"incident_site": {"id": "SITE-01"}, "scenario": "regional-outage"}
    w = build_registered_workflow("NI-2", "network-incident", "incident", observation)
    assert w.payload == {"incident": observation, "scenario": "regional-outage"}
    # Top-level copy (mirrors the strategic factory's ``dict(payload_data)``):
    # the nested dict is a distinct object at the domain key.
    assert w.payload["incident"] is not observation


def test_scenario_absent_defaults_to_none():
    w = build_registered_workflow("NI-3", "network-incident", "incident", {"incident_site": {}})
    assert w.payload["scenario"] is None


def test_extra_payload_is_merged_at_top_level():
    w = build_registered_workflow(
        "NI-4", "network-incident", "incident", {"incident_site": {"id": "S"}},
        extra_payload={"objective_id": "obj-evt-1", "trace_id": "trace-1"},
    )
    assert w.payload["objective_id"] == "obj-evt-1"
    assert w.payload["trace_id"] == "trace-1"
    # Domain payload still nested under the projection key.
    assert w.payload["incident"]["incident_site"]["id"] == "S"


def test_platform_fields_are_populated():
    w = build_registered_workflow("NI-5", "network-incident", "incident", {})
    assert w.jurisdiction
    assert w.agency
    assert w.sla_due_at > w.created_at
