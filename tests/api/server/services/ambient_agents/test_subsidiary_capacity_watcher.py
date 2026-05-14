"""Pitch-h4: subsidiary_capacity_watcher gates new media-pitch-to-win
workflows when the target subsidiary is already running >= 90%
billable utilisation. Idempotent on (subsidiary_id, hour_of_day).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from api.server.services.ambient_agents import subsidiary_capacity_watcher
from api.server.services.event_bus import EventBus
from api.shared.events import FleetEvent


SUBSIDIARY = "ORG-zava-creative"
HEADCOUNT = 20


@dataclass
class _StubWorkflow:
    id: str
    status: str = "in_progress"
    payload: dict[str, Any] = field(default_factory=dict)


class _StubStore:
    def __init__(self, workflows=()):
        self._workflows = list(workflows)

    def list_workflows(self):
        return list(self._workflows)


def _make_watcher(*, hour: int = 10, in_flight_count: int = 0):
    """Build a fresh watcher + bus + capture list."""
    workflows = [
        _StubWorkflow(
            id=f"WF-{i:04d}",
            status="in_progress",
            payload={"subsidiary_id": SUBSIDIARY},
        )
        for i in range(in_flight_count)
    ]
    store = _StubStore(workflows)
    bus = EventBus()
    captured: list[FleetEvent] = []
    bus.on_any(lambda e: captured.append(e))

    watcher = subsidiary_capacity_watcher.SubsidiaryCapacityWatcher(
        headcounts={SUBSIDIARY: HEADCOUNT},
        threshold_pct=90.0,
        hour_provider=lambda: hour,
    )
    watcher.start(bus, store)
    return watcher, bus, captured


def _start_event(workflow_id: str = "PITCH-NEW", subsidiary_id: str | None = SUBSIDIARY):
    payload: dict[str, Any] = {"workflow_type": "media-pitch-to-win"}
    if subsidiary_id is not None:
        payload["subsidiary_id"] = subsidiary_id
    return FleetEvent(
        type="workflow.started",
        workflow_id=workflow_id,
        workflow_type="media-pitch-to-win",
        payload=payload,
        subsidiary_id=subsidiary_id,
    )


def test_high_utilisation_emits_no_capacity_exception():
    # 18/20 = 90.0% — exactly at threshold, MUST emit.
    _watcher, bus, captured = _make_watcher(in_flight_count=18)

    captured.clear()
    bus.emit(_start_event())

    no_caps = [e for e in captured if e.type == "workflow.exception.detected"]
    assert len(no_caps) == 1, (
        f"expected one no_capacity exception; got {[e.model_dump() for e in captured]}"
    )
    payload = no_caps[0].model_dump()
    assert payload["kind"] == "no_capacity"
    assert payload["subsidiary_id"] == SUBSIDIARY
    assert payload["utilisation_pct"] >= 90.0


def test_repeat_in_same_hour_is_suppressed():
    watcher, bus, captured = _make_watcher(in_flight_count=19, hour=10)

    captured.clear()
    bus.emit(_start_event(workflow_id="PITCH-A"))
    bus.emit(_start_event(workflow_id="PITCH-B"))
    bus.emit(_start_event(workflow_id="PITCH-C"))

    no_caps = [e for e in captured if e.type == "workflow.exception.detected"]
    assert len(no_caps) == 1, (
        "same (subsidiary, hour) must emit the no_capacity exception "
        f"exactly once; got {len(no_caps)}"
    )


def test_new_hour_re_emits():
    watcher, bus, captured = _make_watcher(in_flight_count=19, hour=10)

    bus.emit(_start_event(workflow_id="PITCH-A"))
    captured.clear()

    # Advance the watcher's clock to a new hour; same saturation should
    # produce a fresh exception.
    watcher._hour_provider = lambda: 11

    bus.emit(_start_event(workflow_id="PITCH-B"))

    no_caps = [e for e in captured if e.type == "workflow.exception.detected"]
    assert len(no_caps) == 1, (
        f"new hour must re-emit; got {[e.model_dump() for e in captured]}"
    )


def test_healthy_utilisation_emits_nothing():
    # 5/20 = 25% — well under the 90% threshold.
    _, bus, captured = _make_watcher(in_flight_count=5)

    captured.clear()
    bus.emit(_start_event())

    no_caps = [e for e in captured if e.type == "workflow.exception.detected"]
    assert no_caps == [], (
        f"healthy subsidiary must not emit no_capacity; got "
        f"{[e.model_dump() for e in no_caps]}"
    )


def test_non_pitch_workflow_is_ignored():
    """Watcher MUST only react to media-pitch-to-win starts."""
    _, bus, captured = _make_watcher(in_flight_count=19)

    captured.clear()
    bus.emit(FleetEvent(
        type="workflow.started",
        workflow_id="EXP-001",
        workflow_type="expense-claim",
        payload={"workflow_type": "expense-claim", "subsidiary_id": SUBSIDIARY},
        subsidiary_id=SUBSIDIARY,
    ))

    no_caps = [e for e in captured if e.type == "workflow.exception.detected"]
    assert no_caps == []


def test_unknown_subsidiary_is_skipped():
    """A pitch targeting a subsidiary with no headcount on file must
    NOT emit (skipped, not crashed)."""
    _, bus, captured = _make_watcher(in_flight_count=19)

    captured.clear()
    bus.emit(_start_event(subsidiary_id="ORG-unknown"))

    no_caps = [e for e in captured if e.type == "workflow.exception.detected"]
    assert no_caps == []


# --------------------------------------------------------------------------
# (no extra helpers needed)
# --------------------------------------------------------------------------
