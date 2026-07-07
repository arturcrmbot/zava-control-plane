"""Process-wide compose session registry.

v1 is one-run-at-a-time, so an `active` pointer is enough for the MCP tools to
find the session a tool call belongs to. Multi-session would key MCP calls by a
header/URL instead.
"""
from __future__ import annotations

from .session import ComposeSession

_sessions: dict[str, ComposeSession] = {}
_active: str | None = None


def register(session: ComposeSession) -> None:
    global _active
    _sessions[session.id] = session
    _active = session.id


def get(cid: str) -> ComposeSession | None:
    return _sessions.get(cid)


def active() -> ComposeSession | None:
    return _sessions.get(_active) if _active else None


def reset() -> None:
    """Test helper."""
    global _active
    _sessions.clear()
    _active = None
