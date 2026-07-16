"""Blueprint observatory event recorder + playback templates.

Two responsibilities split into one module:

1. ``BlueprintRecorder`` — when started, subscribes to the in-process
   event bus and writes each ``FleetEvent`` (filtered to the same
   observatory event types the page cares about) to a JSONL file under
   ``data/blueprint-recordings/``. One file per ``workflow_id`` so each
   recording is a complete walk of one workflow.

2. ``load_recorded_templates`` — reads the recordings directory and
   returns playback-ready templates the same shape as the hand-coded
   ``_STREAM_TEMPLATES`` in ``blueprint.py``. The demo trickle prefers
   recordings when present, falls back to hand-coded templates when
   absent.

Why an in-process recorder and not a separate script: the EventBus is an
in-memory queue local to the uvicorn process. Anything that wants to see
events has to subscribe to that bus. A standalone script can't.

File layout:

    data/blueprint-recordings/
      README.md
      hiring-2026-05-03-1840.jsonl
      expense-claim-2026-05-03-1841.jsonl

Each JSONL line:

    {"ts_offset_ms": 0,    "event": {"type": "workflow.started", ...}}
    {"ts_offset_ms": 1240, "event": {"type": "durable.step.started", ...}}
    {"ts_offset_ms": 2870, "event": {"type": "agent.completed", ...}}
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.shared.events import FleetEvent
from api.shared.vertical_pack import VerticalRuntime

# The set of event types the observatory surfaces; recordings filter to the
# same set so we never capture noise the page would discard anyway.
RECORDED_TYPES: frozenset[str] = frozenset({
    "workflow.started",
    "durable.workflow.started",
    "durable.step.started",
    "durable.step.completed",
    "durable.executor.invoked",
    "agent.completed",
    "durable.validator.blocked",
    "workflow.exception.detected",
    "workflow.hitl.requested",
    "durable.suspended",
    "durable.workflow.completed",
    "workflow.resolved",
    "workflow.failed",
})


def runtime_recordings_dir(runtime: VerticalRuntime) -> Path:
    override = os.getenv("BLUEPRINT_RECORDINGS_DIR")
    if override:
        return Path(override).expanduser()
    return runtime.data_dir / "blueprint-recordings"


def recording_read_dirs(runtime: VerticalRuntime) -> tuple[Path, ...]:
    return (
        *runtime.pack.recordings.curated_dirs,
        runtime_recordings_dir(runtime),
    )


# --------------------------------------------------------------------------
# Recording side
# --------------------------------------------------------------------------


class BlueprintRecorder:
    """Subscribes to the bus and writes per-workflow JSONL files.

    One instance per running uvicorn process; idempotent ``start`` and
    ``stop`` so the route can be hit repeatedly without duplicating
    subscriptions.

    Each recorded workflow becomes its own JSONL file. We close a
    workflow's file when ``durable.workflow.completed`` or
    ``workflow.resolved`` arrives for that ``workflow_id``, OR when
    ``stop()`` is called. Workflows still mid-flight at stop time are
    still flushed (they will be a partial recording, which is fine —
    playback will replay whatever lines they contain).
    """

    def __init__(self, runtime: VerticalRuntime) -> None:
        self._runtime = runtime
        self._unsubscribe = None  # callable returned by bus.on_any
        self._workflows: dict[str, _Recording] = {}  # workflow_id -> Recording
        # Workflows that have already been written. Subsequent terminal
        # events (e.g. workflow.resolved arriving after
        # durable.workflow.completed) are silently ignored, so we don't
        # reopen the file with a -1 suffix and a single-event payload.
        # Cleared on stop().
        self._closed: set[str] = set()
        self._started_at_ms: float | None = None
        self._lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._unsubscribe is not None

    def start(self, bus) -> dict[str, Any]:
        if self._unsubscribe is not None:
            return {"status": "already running", "workflows_so_far": len(self._workflows)}
        self._workflows = {}
        self._started_at_ms = time.time() * 1000.0

        def _on_event(event: FleetEvent) -> None:
            self._handle(event)

        self._unsubscribe = bus.on_any(_on_event)
        return {
            "status": "started",
            "recordings_dir": str(runtime_recordings_dir(self._runtime)),
        }

    def stop(self) -> dict[str, Any]:
        if self._unsubscribe is None:
            return {"status": "not running"}
        try:
            self._unsubscribe()
        except Exception:
            pass
        self._unsubscribe = None

        # Flush any in-flight workflows. Partial recordings are intentional:
        # they will replay the steps that were captured and stop. Operator
        # can curate by hand if they want to delete short ones.
        flushed: list[str] = []
        for wid, rec in self._workflows.items():
            path = self._write_recording(rec)
            flushed.append(str(path.name))
        completed = len(flushed)
        self._workflows = {}
        self._closed = set()
        self._started_at_ms = None
        return {"status": "stopped", "files_written": completed, "files": flushed}

    def status(self) -> dict[str, Any]:
        return {
            "running": self.is_running,
            "in_flight_workflows": list(self._workflows.keys()),
            "recordings_dir": str(runtime_recordings_dir(self._runtime)),
        }

    def _handle(self, event: FleetEvent) -> None:
        if event.type not in RECORDED_TYPES:
            return
        data = event.model_dump()
        wid = (
            data.get("workflow_id")
            or data.get("workflowId")
            or data.get("instance_id")
            or data.get("instanceId")
        )
        if not wid:
            # Without a workflow_id we can't group; skip. The page also
            # benefits less from such events.
            return

        # Already-closed workflow: a duplicate terminal event arrived
        # (e.g. workflow.resolved after durable.workflow.completed). Drop
        # silently — don't reopen the file.
        if wid in self._closed:
            return

        now_ms = time.time() * 1000.0
        rec = self._workflows.get(wid)
        if rec is None:
            wf_type = data.get("workflow_type") or data.get("workflowType") or "unknown"
            rec = _Recording(workflow_id=wid, workflow_type=wf_type, started_at_ms=now_ms)
            self._workflows[wid] = rec

        ts_offset_ms = int(now_ms - rec.started_at_ms)
        rec.events.append({"ts_offset_ms": ts_offset_ms, "event": data})

        # Workflow-end events: write out and forget. Mark closed so a second
        # terminal event for the same wid doesn't open a fresh file.
        if event.type in (
            "durable.workflow.completed",
            "workflow.resolved",
            "workflow.failed",
        ):
            self._write_recording(rec)
            self._workflows.pop(wid, None)
            self._closed.add(wid)

    def _write_recording(self, rec: "_Recording") -> Path:
        rdir = runtime_recordings_dir(self._runtime)
        rdir.mkdir(parents=True, exist_ok=True)
        # Filename: <workflow_type>-<UTC ISO without colons>-<short id>.jsonl
        # Keep the ID readable: take a 16-char tail (or full id if shorter).
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
        safe_type = "".join(c if c.isalnum() or c in "-_" else "-" for c in (rec.workflow_type or "unknown"))
        cleaned_id = "".join(c if c.isalnum() or c in "-_" else "-" for c in rec.workflow_id)
        safe_id = cleaned_id if len(cleaned_id) <= 16 else cleaned_id[-16:]
        path = rdir / f"{safe_type}-{ts}-{safe_id}.jsonl"
        # Avoid clobbering an exact-second collision.
        suffix = 0
        while path.exists():
            suffix += 1
            path = rdir / f"{safe_type}-{ts}-{safe_id}-{suffix}.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for entry in rec.events:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        return path


class _Recording:
    """In-memory accumulator for one workflow's events."""

    __slots__ = ("workflow_id", "workflow_type", "started_at_ms", "events")

    def __init__(self, workflow_id: str, workflow_type: str, started_at_ms: float):
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type
        self.started_at_ms = started_at_ms
        self.events: list[dict[str, Any]] = []


# --------------------------------------------------------------------------
# Playback side
# --------------------------------------------------------------------------


def load_recorded_templates(runtime: VerticalRuntime) -> list[dict[str, Any]]:
    """Read every JSONL file under data/blueprint-recordings/ and return
    them as templates suitable for the demo stream loop.

    Each returned template:

        {
            "workflow_type":  str,                 # for prefix selection
            "events":         [event_dict, ...],   # original event payloads
            "deltas_ms":      [int, ...],          # gap before each event
            "source":         "recorded",          # debug breadcrumb
            "filename":       str,                 # for logs
        }

    Returns an empty list if the directory doesn't exist or holds no
    parseable files. The caller falls back to hand-coded templates in
    that case.
    """
    templates: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for recordings_dir in recording_read_dirs(runtime):
        if not recordings_dir.exists():
            continue
        for path in sorted(recordings_dir.glob("*.jsonl")):
            events: list[dict[str, Any]] = []
            deltas_ms: list[int] = []
            prev_offset: int | None = None
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        entry = json.loads(line)
                        offset = int(entry.get("ts_offset_ms", 0))
                        events.append(entry["event"])
                        if prev_offset is None:
                            deltas_ms.append(0)
                        else:
                            deltas_ms.append(max(0, offset - prev_offset))
                        prev_offset = offset
            except (OSError, ValueError, KeyError) as error:
                raise ValueError(
                    f"invalid Blueprint recording {path}: {error}"
                ) from error
            if not events:
                continue
            workflow_type = (
                events[0].get("workflow_type")
                or events[0].get("workflowType")
                or "unknown"
            )
            if workflow_type not in runtime.pack.domains:
                raise ValueError(
                    f"recording workflow {workflow_type!r} is not in active "
                    f"vertical {runtime.pack.name!r}: {path.name}"
                )
            workflow_id = (
                events[0].get("workflow_id")
                or events[0].get("workflowId")
            )
            key = (path.name, workflow_id)
            if key in seen:
                continue
            seen.add(key)
            templates.append({
                "workflow_type": workflow_type,
                "events": events,
                "deltas_ms": deltas_ms,
                "source": "recorded",
                "filename": path.name,
            })
    return templates
