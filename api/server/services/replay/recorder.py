"""Recorder: captures a live session to a replay tape archive.

Option A mutation timestamps: mutations are stamped *when drained from the
MutationBus*, which happens inside _on_event() (after recording the event) and
again during periodic flushes and final stop().  This keeps mutation.t aligned
with the triggering event's approximate wall-clock offset from t0.  Mutations
that arrive between events (rare) are captured during flush/stop drains and
receive the timestamp of that drain pass instead.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import shutil
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

from api.server.services.replay.mutation_bus import MutationBus, get_active_bus, set_active_bus
from api.server.services.replay.snapshot import take_snapshot
from api.server.services.replay.tape_format import (
    EVENTS_NAME,
    META_NAME,
    MUTATIONS_NAME,
    SNAPSHOT_DIR,
    TAPE_FORMAT_VERSION,
    EventRecord,
    MutationRecord,
    TapeMeta,
)
from api.server.state import app_state
from api.shared.events import FleetEvent


logger = logging.getLogger(__name__)


class Recorder:
    def __init__(
        self,
        *,
        out_path: Path,
        app_sha: str | None = None,
        snapshot_dir: Path | None = None,
        flush_interval_s: float = 300.0,
    ) -> None:
        self._out_path = out_path
        self._app_sha = app_sha
        self._snapshot_dir = snapshot_dir
        self._flush_interval_s = flush_interval_s

        self._work_dir: Path | None = None
        self._owns_work_dir = False
        self._start_mono: float = 0.0
        self._mutation_bus: MutationBus | None = None
        self._off: object = None  # unsubscribe thunk from app_state.bus.on_any

        self._event_buf: list[EventRecord] = []
        self._mutation_buf: list[MutationRecord] = []
        self._flush_task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start(self) -> None:
        """Set up working directory, snapshot, bus hooks, and flush task."""
        if self._snapshot_dir is not None:
            self._work_dir = self._snapshot_dir
            self._work_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._work_dir = self._out_path.parent / f".recorder-{secrets.token_hex(4)}"
            self._work_dir.mkdir(parents=True, exist_ok=False)
            self._owns_work_dir = True

        try:
            snap_dir = self._work_dir / SNAPSHOT_DIR.rstrip("/")
            take_snapshot(snap_dir)

            self._start_mono = time.monotonic()

            self._mutation_bus = MutationBus()
            set_active_bus(self._mutation_bus)

            self._off = app_state.bus.on_any(self._on_event)
            self._flush_task = asyncio.create_task(self._flush_loop())
        except Exception:
            if self._off is not None:
                self._off()  # type: ignore[operator]
                self._off = None
            if get_active_bus() is self._mutation_bus:
                set_active_bus(None)
            self._mutation_bus = None
            self._cleanup_work_dir()
            raise

    def _on_event(self, ev: FleetEvent) -> None:
        """Record one FleetEvent, then drain pending mutations."""
        t = time.monotonic() - self._start_mono
        record = EventRecord(t=t, event=ev.model_dump(mode="json"))
        self._event_buf.append(record)
        # Drain mutations now so their timestamps align with this event.
        self._drain_mutations()

    def _drain_mutations(self) -> None:
        """Stamp and move all pending mutation bus entries into the buffer."""
        bus = self._mutation_bus
        if bus is None or not bus.entries:
            return
        t = time.monotonic() - self._start_mono
        for entry in bus.drain():
            record = MutationRecord(
                t=t,
                op=entry["op"],
                kind=entry["kind"],
                id=entry["id"],
                patch=entry["patch"],
            )
            self._mutation_buf.append(record)

    async def _flush_buffers(self) -> None:
        """Append event and mutation buffers to their ndjson files, then clear."""
        assert self._work_dir is not None

        events_path = self._work_dir / EVENTS_NAME
        mutations_path = self._work_dir / MUTATIONS_NAME

        events_to_write = self._event_buf[:]
        mutations_to_write = self._mutation_buf[:]

        if events_to_write:
            with events_path.open("a", encoding="utf-8") as fh:
                for record in events_to_write:
                    fh.write(record.model_dump_json() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            del self._event_buf[: len(events_to_write)]

        if mutations_to_write:
            with mutations_path.open("a", encoding="utf-8") as fh:
                for record in mutations_to_write:
                    fh.write(record.model_dump_json() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            del self._mutation_buf[: len(mutations_to_write)]

    def _cleanup_work_dir(self) -> None:
        if self._owns_work_dir and self._work_dir is not None:
            shutil.rmtree(self._work_dir, ignore_errors=True)
            self._work_dir = None
            self._owns_work_dir = False

    async def _flush_loop(self) -> None:
        """Periodic flush task."""
        try:
            while True:
                await asyncio.sleep(self._flush_interval_s)
                try:
                    self._drain_mutations()
                    await self._flush_buffers()
                except Exception:
                    logger.exception("Recorder flush failed; retaining buffered records for retry")
                    continue
        except asyncio.CancelledError:
            pass

    async def stop(self) -> Path:
        """Stop recording, write tape archive, and return out_path."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        if self._off is not None:
            self._off()  # type: ignore[operator]
            self._off = None

        if get_active_bus() is self._mutation_bus:
            set_active_bus(None)

        try:
            # Final drain to capture any mutations that arrived after the last event.
            self._drain_mutations()
            await self._flush_buffers()

            duration_s = time.monotonic() - self._start_mono
            tape_id = "tape_" + secrets.token_hex(4)
            recorded_at = datetime.now(timezone.utc).isoformat()

            meta = TapeMeta(
                tape_id=tape_id,
                recorded_at=recorded_at,
                duration_s=duration_s,
                version=TAPE_FORMAT_VERSION,
                app_sha=self._app_sha,
                selected_vertical=app_state.runtime.pack.name,
            )

            assert self._work_dir is not None
            meta_path = self._work_dir / META_NAME
            with meta_path.open("w", encoding="utf-8") as fh:
                fh.write(meta.model_dump_json())
                fh.flush()
                os.fsync(fh.fileno())

            # Ensure ndjson files exist (even if empty).
            (self._work_dir / EVENTS_NAME).touch()
            (self._work_dir / MUTATIONS_NAME).touch()

            self._out_path.parent.mkdir(parents=True, exist_ok=True)
            with tarfile.open(self._out_path, "w:gz") as tf:
                for path in sorted(self._work_dir.rglob("*")):
                    if path.is_file():
                        arcname = "./" + path.relative_to(self._work_dir).as_posix()
                        tf.add(path, arcname=arcname)

            return self._out_path
        finally:
            self._cleanup_work_dir()
