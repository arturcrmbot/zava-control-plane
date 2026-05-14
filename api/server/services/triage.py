from __future__ import annotations
import time
from api.shared.events import FleetEvent, wakes_fleet_manager
from api.shared import domains as _registry


class Triage:
    def __init__(self) -> None:
        self._recent_dups: list[tuple[str, float]] = []

    def should_wake(self, e: FleetEvent) -> bool:
        # Phase 4 of feature-fleet-domain-substrate-1: in addition to the
        # platform-wide WAKE_TYPES (workflow.exception.detected, hitl,
        # SLA breach, anomaly, tick, claim.routed.red), wake the FM on
        # any per-domain wake hint declared in the registry.
        if wakes_fleet_manager(e):
            return True
        return e.type in _registry.all_wake_hints()

    def observe(self, e: FleetEvent, now: float | None = None) -> None:
        now = now if now is not None else time.time()
        if e.type == "workflow.exception.detected" and getattr(e, "category", None) == "duplicate-invoice":
            self._recent_dups.append((e.workflow_id or "", now))
            self._recent_dups = [(w, t) for w, t in self._recent_dups if now - t <= 60]

    def detect_anomaly(self, now: float | None = None) -> dict | None:
        now = now if now is not None else time.time()
        dups = [(w, t) for w, t in self._recent_dups if now - t <= 60]
        if len(dups) >= 3:
            return {"pattern": "duplicate-burst", "workflow_ids": [w for w, _ in dups]}
        return None
