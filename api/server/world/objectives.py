"""Deterministic objective lifecycle over the simulation journal.

The manager opens one :class:`~api.server.world.model.Objective` per real
sensor event, deduplicated by ``(type, target)`` while active, and walks it
through a strict transition table. Every transition appends an
``objective.<status>`` event to the same causal trace as the sensor that
opened it, so the objective lifecycle is visible in the existing journal and
snapshot without any new stream.

No background task, no priority queue, no agent logic: the manager is a pure
synchronous state machine driven entirely by its callers (the world bridge and
command gateway).
"""
from __future__ import annotations

from dataclasses import replace

from api.server.world.model import Objective
from api.server.world.registry import WorldPackRegistration
from api.server.world.runtime import SimulationRuntime

# Strict allowed-state table. Non-terminal states may fail or be superseded at
# any point; the happy path is open → claimed → acting → evaluating → resolved.
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"claimed", "superseded", "failed"}),
    "claimed": frozenset({"acting", "superseded", "failed"}),
    "acting": frozenset({"evaluating", "superseded", "failed"}),
    "evaluating": frozenset({"resolved", "failed", "superseded"}),
    "resolved": frozenset(),
    "failed": frozenset(),
    "superseded": frozenset(),
}
_TERMINAL: frozenset[str] = frozenset({"resolved", "failed", "superseded"})
TERMINAL_STATUSES = _TERMINAL


def objective_id(sensor_event_id: str) -> str:
    """Deterministic objective id for a sensor event id."""
    return f"obj-{sensor_event_id}"


def _event_type(status: str) -> str:
    """Journal event name for a status (``open`` reads as the past-tense opened)."""
    return "objective.opened" if status == "open" else f"objective.{status}"


class ObjectiveManager:
    """Owns every objective for one live world; writes lifecycle to the journal."""

    def __init__(self, runtime: SimulationRuntime) -> None:
        self._runtime = runtime
        self._objectives: dict[str, Objective] = {}
        self._order: list[str] = []
        self._active_by_key: dict[tuple[str, str | None], str] = {}
        self._target_by_id: dict[str, str | None] = {}
        self._last_event_id: dict[str, str] = {}

    def open(
        self,
        sensor_event: dict,
        registration: WorldPackRegistration,
        *,
        owner_function: str,
        priority: int = 0,
        deadline: float | None = None,
    ) -> Objective:
        """Open (or return the existing active) objective for a sensor event.

        Deterministic id ``obj-{sensor_event_id}``. If a non-terminal objective
        already exists for this ``(type, target)``, it is returned unchanged and
        no second ``objective.opened`` is journalled.
        """
        target = sensor_event.get("target_id")
        objective_type = registration.objective_type
        key = (objective_type, target)
        existing_id = self._active_by_key.get(key)
        if existing_id is not None:
            return self._objectives[existing_id]

        sensor_event_id = sensor_event["event_id"]
        objective = Objective(
            id=objective_id(sensor_event_id),
            type=objective_type,
            trace_id=sensor_event["trace_id"],
            owner_function=owner_function,
            priority=priority,
            status="open",
            created_at=self._runtime.now,
            deadline=deadline,
            evidence_event_ids=(sensor_event_id,),
            allowed_command_types=registration.allowed_command_types,
        )
        self._objectives[objective.id] = objective
        self._order.append(objective.id)
        self._active_by_key[key] = objective.id
        self._target_by_id[objective.id] = target
        self._emit(objective, cause_event_id=sensor_event_id)
        return objective

    def transition(
        self,
        objective_id: str,
        to_status: str,
        *,
        claimed_by: str | None = None,
        cause_event_id: str | None = None,
        evidence_event_id: str | None = None,
        payload: dict | None = None,
    ) -> Objective:
        """Move an objective to ``to_status`` per the strict table and journal it.

        Raises ``KeyError`` for an unknown objective and ``ValueError`` for a
        transition not permitted from the current status.
        """
        objective = self._objectives[objective_id]
        if to_status not in _ALLOWED_TRANSITIONS[objective.status]:
            raise ValueError(
                f"objective {objective_id} cannot transition {objective.status} → {to_status}"
            )
        if to_status == "claimed" and claimed_by is None and objective.claimed_by is None:
            raise ValueError("claimed transition requires claimed_by")

        changes: dict = {"status": to_status}
        if claimed_by is not None:
            changes["claimed_by"] = claimed_by
        if evidence_event_id is not None:
            changes["evidence_event_ids"] = objective.evidence_event_ids + (evidence_event_id,)
        updated = replace(objective, **changes)
        self._objectives[objective_id] = updated

        if to_status in _TERMINAL:
            key = (updated.type, self._target_by_id.get(objective_id))
            if self._active_by_key.get(key) == objective_id:
                del self._active_by_key[key]

        cause = cause_event_id or self._last_event_id.get(objective_id)
        self._emit(updated, cause_event_id=cause, extra_payload=payload)
        return updated

    def get(self, objective_id: str) -> Objective | None:
        return self._objectives.get(objective_id)

    def all(self) -> list[Objective]:
        return [self._objectives[oid] for oid in self._order]

    def active(self) -> list[Objective]:
        return [o for o in self.all() if o.status not in _TERMINAL]

    def _emit(
        self,
        objective: Objective,
        *,
        cause_event_id: str | None,
        extra_payload: dict | None = None,
    ):
        payload = objective.to_dict()
        if extra_payload:
            payload = {**payload, **extra_payload}
        event = self._runtime.emit(
            _event_type(objective.status),
            actor_id=objective.owner_function,
            target_id=self._target_by_id.get(objective.id),
            cause_event_id=cause_event_id,
            trace_id=objective.trace_id,
            payload=payload,
        )
        self._last_event_id[objective.id] = event.event_id
        return event
