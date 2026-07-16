"""Hourly story-pack writer (pitch-j5).

Mirrors the H1/H2 module-singleton pattern so uvicorn ``--reload``
cycles don't accumulate tick loops. Ticks every 60 seconds and calls
``story_pack.write_hourly_story()`` whenever the hour rolls over —
the writer itself is idempotent on the (hour, hour+1) key, so a
double-fire is harmless.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
from pathlib import Path

from api.server.services import story_pack

log = logging.getLogger(__name__)


DEFAULT_TICK_SECONDS: float = 60.0


class StoryPackWriter:
    """Singleton ambient agent that writes hourly story packs to disk."""

    def __init__(
        self,
        *,
        base_dir: Path | None = None,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        self._base_dir = base_dir or story_pack.default_base_dir()
        self._tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None
        # Track the last hour we successfully wrote so a single tick
        # storm (e.g. clock skew at boot) doesn't scribble the same
        # file twice — write_hourly_story is already idempotent on
        # contents, but skipping the no-op call keeps logs quiet.
        self._last_written_hour: _dt.datetime | None = None

    # ------------------------------------------------------------------
    # core tick — directly testable without an event loop
    # ------------------------------------------------------------------

    def tick(self, *, now_ts: float | None = None) -> Path | None:
        """Write the previous hour's story when the hour rolls over.

        Returns the path written this tick, or ``None`` when the hour
        boundary hasn't moved since the last successful write.
        """
        if now_ts is None:
            now_ts = _dt.datetime.now(tz=_dt.timezone.utc).timestamp()
        current_hour = _dt.datetime.fromtimestamp(
            now_ts, tz=_dt.timezone.utc
        ).replace(minute=0, second=0, microsecond=0)
        if self._last_written_hour == current_hour:
            return None
        try:
            path = story_pack.write_hourly_story(
                base_dir=self._base_dir, now_ts=now_ts
            )
        except Exception:
            log.exception("story_pack_writer: write_hourly_story raised")
            return None
        self._last_written_hour = current_hour
        return path

    # ------------------------------------------------------------------
    # background loop lifecycle
    # ------------------------------------------------------------------

    def start(self, *, base_dir: Path | None = None) -> None:
        """Schedule the per-minute tick loop on the running event loop."""
        self.stop()
        if base_dir is not None:
            self._base_dir = base_dir
        try:
            self._task = asyncio.create_task(self._run_forever())
        except RuntimeError:
            # No running loop (e.g. import-time call). Skip silently.
            log.debug("story_pack_writer: no running loop; tick loop not scheduled")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run_forever(self) -> None:
        while True:
            try:
                self.tick()
            except Exception:
                log.exception("story_pack_writer: tick crashed (swallowed)")
            try:
                await asyncio.sleep(self._tick_seconds)
            except asyncio.CancelledError:
                raise


# Module-level singleton wired by api.server.main lifespan.
_WRITER = StoryPackWriter()


def start(*, base_dir: Path | None = None) -> None:
    """Wire the singleton writer and start its tick loop."""
    _WRITER.start(base_dir=base_dir)


def stop() -> None:
    """Cancel the singleton writer's tick loop."""
    _WRITER.stop()


def _reset_for_tests() -> None:
    """Test-only: clear the last-written-hour memo."""
    _WRITER._last_written_hour = None
