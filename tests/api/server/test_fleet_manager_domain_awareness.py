"""FM domain awareness — templated catalogue + triage wake-hint membership.

Per TASK-023 of plan/feature-fleet-domain-substrate-1.md.
"""
from __future__ import annotations

from api.server.services.fleet_manager_service import _domain_catalogue_section
from api.server.services.triage import Triage
from api.shared import domains as registry
from api.shared.events import FleetEvent


def test_skill_text_lists_every_workflow_type():
    text = _domain_catalogue_section()
    for wt in registry.DOMAINS:
        assert wt in text, f"{wt} missing from FM domain catalogue"


def test_skill_text_lists_every_operator_surface():
    text = _domain_catalogue_section()
    for d in registry.DOMAINS.values():
        assert d.operator_surface in text


def test_triage_wakes_on_registered_wake_hints():
    t = Triage()
    for d in registry.DOMAINS.values():
        for wh in d.wake_hints:
            assert t.should_wake(FleetEvent(type=wh.event, workflow_id="X")), (
                f"triage failed to wake on registered hint {wh.event!r}"
            )


def test_triage_does_not_wake_on_unknown_event():
    t = Triage()
    assert not t.should_wake(FleetEvent(type="nothing.special", workflow_id="X"))
