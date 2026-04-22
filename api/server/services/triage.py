from __future__ import annotations
import time
from api.shared.events import FleetEvent, wakes_fleet_manager


class Triage:
    def __init__(self) -> None:
        self._recent_dups: list[tuple[str, float]] = []

    def should_wake(self, e: FleetEvent) -> bool:
        return wakes_fleet_manager(e)

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
