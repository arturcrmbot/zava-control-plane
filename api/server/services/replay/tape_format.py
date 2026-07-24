from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# Tape layout constants
META_NAME = "meta.json"
SNAPSHOT_DIR = "snapshot_t0/"
EVENTS_NAME = "events.ndjson"
MUTATIONS_NAME = "mutations.ndjson"
TAPE_FORMAT_VERSION = 1


class TapeMeta(BaseModel):
    """Metadata for a replay tape recording."""

    model_config = ConfigDict(extra="forbid")

    tape_id: str
    recorded_at: str
    duration_s: float
    version: int = TAPE_FORMAT_VERSION
    app_sha: str | None = None


class EventRecord(BaseModel):
    """A single event in a replay tape."""

    model_config = ConfigDict(extra="forbid")

    t: float
    event: dict[str, Any]


class MutationRecord(BaseModel):
    """A single state mutation in a replay tape."""

    model_config = ConfigDict(extra="forbid")

    t: float
    op: Literal["upsert", "delete", "replace", "append"]
    kind: Literal[
        "workflow",
        "phases",
        "exception",
        "memory",
        "lesson",
        "decision",
        "insight",
        "entity",
        "audit",
        "span",
        "mcp_call",
    ]
    id: str
    patch: dict[str, Any]
