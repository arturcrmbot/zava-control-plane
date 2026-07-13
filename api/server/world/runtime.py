"""Generic deterministic SimPy runtime and append-only causal journal."""
from __future__ import annotations

import json
import random
from collections.abc import Generator
from pathlib import Path
from typing import Any

import simpy

from api.server.world.model import SimulationEvent


class SimulationRuntime:
    def __init__(self, seed: int) -> None:
        self.seed = seed
        self.env = simpy.Environment()
        self.rng = random.Random(seed)
        self.journal: list[SimulationEvent] = []
        self.status = "paused"
        self._seq = 0

    @property
    def now(self) -> float:
        return float(self.env.now)

    def process(self, generator: Generator):
        return self.env.process(generator)

    def emit(
        self,
        event_type: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        cause_event_id: str | None = None,
        trace_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> SimulationEvent:
        self._seq += 1
        event_id = f"evt-{self._seq:08d}"
        event = SimulationEvent(
            seq=self._seq,
            event_id=event_id,
            sim_time=self.now,
            type=event_type,
            actor_id=actor_id,
            target_id=target_id,
            cause_event_id=cause_event_id,
            trace_id=trace_id or event_id,
            payload=dict(payload or {}),
        )
        self.journal.append(event)
        return event

    def step(self) -> list[SimulationEvent]:
        if self.env.peek() == float("inf"):
            self.status = "completed"
            return []
        before = len(self.journal)
        self.status = "running"
        self.env.step()
        if self.env.peek() == float("inf"):
            self.status = "completed"
        else:
            self.status = "paused"
        return self.journal[before:]

    def run_until(self, until: float) -> list[SimulationEvent]:
        if until < self.now:
            raise ValueError(f"cannot run backwards from {self.now} to {until}")
        before = len(self.journal)
        self.status = "running"
        while self.env.peek() <= until:
            self.env.step()
        self.status = "completed" if self.env.peek() == float("inf") else "paused"
        return self.journal[before:]

    def run_events(self, count: int) -> list[SimulationEvent]:
        before = len(self.journal)
        for _ in range(count):
            if self.env.peek() == float("inf"):
                self.status = "completed"
                break
            self.step()
        return self.journal[before:]

    def pause(self) -> None:
        self.status = "paused"

    def canonical_journal(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.journal]

    def export_ndjson(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in self.canonical_journal()),
            encoding="utf-8",
        )
        return output
