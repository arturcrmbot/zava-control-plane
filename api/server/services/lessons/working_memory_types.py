"""Value types for the working memory tier."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Literal, Optional


WorkingNoteKind = Literal[
    "observation",
    "decision",
    "tool_call",
    "surprise",
    "lesson_used",   # emitted by _wrapper when an active lesson is included in the agent's system prompt
]


@dataclass(frozen=True)
class WorkingNote:
    """A scratchpad note from one agent invocation."""
    id: str
    workflow_id: str
    agent_skill: str
    kind: WorkingNoteKind
    body: str
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    consumed_by_dream_pass: Optional[str] = None

    def __post_init__(self) -> None:
        from typing import get_args
        if self.kind not in get_args(WorkingNoteKind):
            raise ValueError(f"unknown WorkingNoteKind {self.kind!r}")

    def mark_consumed(self, *, dream_pass_id: str) -> "WorkingNote":
        return replace(self, consumed_by_dream_pass=dream_pass_id)
