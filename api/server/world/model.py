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
