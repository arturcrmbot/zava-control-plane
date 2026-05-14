from __future__ import annotations
from collections import defaultdict
from typing import Callable
from api.shared.events import FleetEvent, FleetEventType

Handler = Callable[[FleetEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._typed: dict[str, list[Handler]] = defaultdict(list)
        self._any: list[Handler] = []

    def on(self, event_type: FleetEventType, handler: Handler) -> Callable[[], None]:
        self._typed[event_type].append(handler)
        def off() -> None:
            try:
                self._typed[event_type].remove(handler)
            except ValueError:
                pass
        return off

    def on_any(self, handler: Handler) -> Callable[[], None]:
        self._any.append(handler)
        def off() -> None:
            try:
                self._any.remove(handler)
            except ValueError:
                pass
        return off

    def emit(self, event: FleetEvent) -> None:
        for h in list(self._typed.get(event.type, [])):
            try:
                h(event)
            except Exception:
                pass
        for h in list(self._any):
            try:
                h(event)
            except Exception:
                pass
