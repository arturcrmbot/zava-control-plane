from __future__ import annotations
import time as _time
from typing import Any


class AuditLogger:
    def __init__(self) -> None:
        self._entries: list[dict] = []

    def log(self, action: str, details: Any) -> None:
        self._entries.append({"action": action, "details": details, "timestamp": _time.time()})

    def list(self) -> list[dict]:
        return list(self._entries)
