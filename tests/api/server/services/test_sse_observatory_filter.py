"""The Org Building (IP1, TASK-002) — SSE relay filter widening.

Confirms that the agentic-org event types listed in the spec all flow
through ``/api/blueprint/stream`` (the observatory SSE route consumed by
``useObservatory``).
"""
from __future__ import annotations

from api.server.routes.blueprint import _OBSERVATORY_TYPES, _normalise_event
from api.shared.events import FleetEvent


_NEW_AGENTIC_ORG_TYPES = (
    "entity.upserted",
    "entity.linked",
    "decision.recorded",
    "ambient.decided",
    "cadence.tick",
    "workflow.sub_spawned",
    "entity.write.failed",
    "entity.write.killed",
    "governance.find_entities",
    "governance.find_entities.denied",
)


def test_widened_filter_includes_all_new_event_types():
    for t in _NEW_AGENTIC_ORG_TYPES:
        assert t in _OBSERVATORY_TYPES, f"{t} should relay through observatory SSE"


def test_normalise_event_passes_new_types_through():
    """``_normalise_event`` returns ``None`` for any unrelayed type. A
    non-None return for each new type proves the filter widening is
    actually applied at the relay layer (not just declared in the set)."""
    for t in _NEW_AGENTIC_ORG_TYPES:
        ev = FleetEvent(type=t, workflow_id="WF-TEST")
        out = _normalise_event(ev)
        assert out is not None, f"{t} should not be filtered out"
        assert out["type"] == t
