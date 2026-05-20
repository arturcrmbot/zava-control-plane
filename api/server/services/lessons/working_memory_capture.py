"""Capture agent session events into working memory.

Subscribes to the existing `agent.completed` FleetEvent stream and the
tool-call events emitted by `_wrapper.py`. Turns each session into a
small bundle of WorkingNotes: one `decision` (the parsed response), one
`tool_call` per invocation. The dream pass reads these later.

This module is *passive*: it does not change the agent runtime, it only
turns events into structured notes the dream pass can consume.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from api.server.services.lessons.working_memory_store import WorkingMemoryStore
from api.server.services.lessons.working_memory_types import WorkingNote


class WorkingMemoryCapture:
    def __init__(self, *, store: WorkingMemoryStore) -> None:
        self._store = store

    def on_agent_completed(
        self,
        *,
        workflow_id: str | None,
        agent_skill: str,
        response_text: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        if not workflow_id:
            return

        decision_body = self._summarise_decision(response_text)
        self._store.add(WorkingNote(
            id=f"WN-{uuid.uuid4()}",
            workflow_id=workflow_id,
            agent_skill=agent_skill,
            kind="decision",
            body=decision_body,
        ))

        for tc in tool_calls:
            tool = str(tc.get("tool", "unknown"))
            latency = tc.get("latency_ms")
            args_summary = self._summarise_tool_value(tc.get("args"))
            result_summary = self._summarise_tool_value(tc.get("result"))
            header = f"called {tool}" + (f" ({latency}ms)" if latency is not None else "")
            body = header
            if args_summary:
                body += f"\n  args: {args_summary}"
            if result_summary:
                body += f"\n  result: {result_summary}"
            self._store.add(WorkingNote(
                id=f"WN-{uuid.uuid4()}",
                workflow_id=workflow_id,
                agent_skill=agent_skill,
                kind="tool_call",
                body=body,
            ))

    @staticmethod
    def _summarise_tool_value(raw: Any, *, max_chars: int = 200) -> str:
        """Compact a tool arg or result blob to a single line of at most max_chars.

        Strings are JSON-quoted on a best-effort basis to surface structure;
        dicts/lists are json.dumps'd; everything else is str()-ified. Trailing
        truncation marker '…' so a proposer can tell when content was clipped.
        """
        if raw is None:
            return ""
        if isinstance(raw, (dict, list)):
            try:
                text = json.dumps(raw, separators=(",", ":"), default=str)
            except Exception:
                text = str(raw)
        else:
            text = str(raw)
        text = text.replace("\n", " ").strip()
        if len(text) > max_chars:
            return text[: max_chars - 1] + "…"
        return text

    @staticmethod
    def _summarise_decision(response_text: str) -> str:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            return response_text[:240]
        if isinstance(parsed, dict):
            decision = parsed.get("decision")
            rationale = parsed.get("rationale") or parsed.get("reason")
            if decision and rationale:
                return f"{decision}: {rationale}"
            if decision:
                return f"decision={decision}"
        return response_text[:240]


# Module-level singleton for the agent runtime to share. Default is an
# in-memory store; production wires a Mem0WorkingMemoryStore via
# `set_default_capture()` at app boot.
_DEFAULT: WorkingMemoryCapture | None = None


def get_default_capture() -> WorkingMemoryCapture:
    """Lazy-init in-process singleton used by `_wrapper.py`."""
    global _DEFAULT
    if _DEFAULT is None:
        from api.server.services.lessons.working_memory_store import (
            InMemoryWorkingMemoryStore,
        )
        _DEFAULT = WorkingMemoryCapture(store=InMemoryWorkingMemoryStore())
    return _DEFAULT


def set_default_capture(capture: WorkingMemoryCapture) -> None:
    """App-boot hook to swap in a real Mem0-backed store."""
    global _DEFAULT
    _DEFAULT = capture


def _reset_default_for_tests() -> None:
    global _DEFAULT
    _DEFAULT = None
