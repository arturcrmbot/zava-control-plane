"""Generic wire records shared by simulation scenarios, APIs and replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SimulationEvent:
    seq: int
    event_id: str
    sim_time: float
    type: str
    actor_id: str | None
    target_id: str | None
    cause_event_id: str | None
    trace_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class SimulationCommand:
    command_id: str
    trace_id: str
    issued_by: str
    type: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Objective lifecycle statuses. The first four are non-terminal; the last three
# are terminal. The ObjectiveManager owns the allowed transitions between them.
OBJECTIVE_STATUSES: tuple[str, ...] = (
    "open",
    "claimed",
    "acting",
    "evaluating",
    "resolved",
    "failed",
    "superseded",
)


@dataclass(frozen=True, slots=True)
class Objective:
    """An immutable unit of intent opened from a real sensor event.

    Deduplicated by ``(type, target)`` while active, carried through a strict
    ``open → claimed → acting → evaluating → resolved`` lifecycle, and always
    stamped with the originating sensor ``trace_id`` so every downstream
    objective/command event stays on the same causal trace.
    """

    id: str
    type: str
    trace_id: str
    owner_function: str
    priority: int
    status: str
    created_at: float
    deadline: float | None
    evidence_event_ids: tuple[str, ...]
    allowed_command_types: frozenset[str]
    claimed_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_event_ids"] = list(self.evidence_event_ids)
        data["allowed_command_types"] = sorted(self.allowed_command_types)
        return data


@dataclass(frozen=True, slots=True)
class Evaluation:
    """An immutable evaluation opened when an accepted command starts changing
    the world. It captures the objective's baseline sensor measurements so a
    later coupled slice can judge effectiveness; for now it only ever reaches
    ``started`` (no effectiveness claim, no policy change).
    """

    id: str
    objective_id: str
    trace_id: str
    command_id: str
    started_at: float
    baseline: dict[str, Any]
    status: str = "started"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
