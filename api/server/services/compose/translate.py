"""Pure translation: ACP `session/update` params -> normalized event dicts.

The normalized schema is the stable contract between the bridge and the UI.
Keeping this a pure function makes it trivially testable against recorded ACP
traces with no live agent.
"""
from __future__ import annotations

from typing import Any

_KIND_MAP = {
    "edit": "edit", "create": "edit", "write": "edit",
    "read": "read", "search": "search", "execute": "execute",
}


def _text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return content.get("text", "")
    if isinstance(content, list):
        return "".join(_text(c) for c in content)
    return ""


def _kind(k: Any) -> str:
    return _KIND_MAP.get(k, "other")


def _tool_extras(upd: dict) -> dict:
    extras: dict[str, Any] = {}
    locs = upd.get("locations") or []
    if locs and isinstance(locs[0], dict) and locs[0].get("path"):
        extras["path"] = locs[0]["path"]
    for c in upd.get("content") or []:
        if isinstance(c, dict) and c.get("type") == "diff":
            extras["diff"] = {"old": c.get("oldText", ""), "new": c.get("newText", "")}
            if "path" not in extras and c.get("path"):
                extras["path"] = c["path"]
    raw = upd.get("rawOutput") or {}
    if isinstance(raw, dict) and raw.get("content"):
        extras["output"] = raw["content"]
    return extras


def translate_update(params: dict) -> list[dict]:
    """Translate one ACP `session/update` notification's params into 0+ events."""
    upd = (params or {}).get("update") or {}
    kind = upd.get("sessionUpdate")

    if kind == "agent_message_chunk":
        return [{"type": "narration", "text": _text(upd.get("content")), "partial": True}]
    if kind == "agent_thought_chunk":
        return [{"type": "thought", "text": _text(upd.get("content")), "partial": True}]
    if kind == "tool_call":
        return [{
            "type": "tool", "id": upd.get("toolCallId"), "title": upd.get("title"),
            "kind": _kind(upd.get("kind")), "status": upd.get("status", "pending"),
            **_tool_extras(upd),
        }]
    if kind == "tool_call_update":
        return [{
            "type": "tool", "id": upd.get("toolCallId"),
            "status": upd.get("status"), **_tool_extras(upd),
        }]
    if kind == "plan":
        return [{"type": "plan", "entries": [
            {"title": e.get("title") or e.get("content"), "status": e.get("status")}
            for e in (upd.get("entries") or [])
        ]}]
    return []
