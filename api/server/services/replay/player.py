from __future__ import annotations

import asyncio
import collections
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable

from api.server.services.replay.tape_format import EventRecord, MutationRecord, TapeMeta
from api.server.services.replay.tape_loader import TapeLoader
from api.shared.events import FleetEvent

logger = logging.getLogger(__name__)


class Player:
    def __init__(
        self,
        loader: TapeLoader,
        *,
        restart_pause_s: float = 3.0,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if loader.meta is None:
            raise ValueError("TapeLoader must be loaded before creating Player")

        self.loader = loader
        self.meta: TapeMeta = loader.meta
        self._restart_pause_s = restart_pause_s
        self._sleep = sleep_fn
        self._clock = clock_fn
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._cycle_started_at: float = 0.0
        self._current_t: float = 0.0

    async def start(self) -> None:
        from api.server.services.replay.hydrate import hydrate_from_snapshot

        self._stop_event.clear()
        hydrate_from_snapshot(self.loader)
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        from api.server.state import app_state
        from api.server.services.replay.hydrate import hydrate_from_snapshot

        while not self._stop_event.is_set():
            events_remaining = collections.deque(self.loader.iter_events())
            mutations_remaining = collections.deque(self.loader.iter_mutations())
            self._cycle_started_at = self._clock()
            self._current_t = 0.0

            while (events_remaining or mutations_remaining) and not self._stop_event.is_set():
                next_t = min(
                    events_remaining[0].t if events_remaining else float("inf"),
                    mutations_remaining[0].t if mutations_remaining else float("inf"),
                )
                elapsed = self._clock() - self._cycle_started_at
                if await self._sleep_until_or_stop(next_t - elapsed):
                    break

                self._current_t = next_t
                if mutations_remaining and (
                    not events_remaining or mutations_remaining[0].t <= events_remaining[0].t
                ):
                    self._apply_mutation(mutations_remaining.popleft())
                else:
                    self._emit_event(events_remaining.popleft(), app_state)

            if self._stop_event.is_set():
                break

            self._emit_restart_pending(app_state)
            if await self._sleep_until_or_stop(self._restart_pause_s):
                break
            try:
                hydrate_from_snapshot(self.loader)
            except Exception:
                logger.exception("Failed to re-hydrate from snapshot between replay cycles; continuing")

    async def _sleep_until_or_stop(self, delay_s: float) -> bool:
        if delay_s <= 0:
            return self._stop_event.is_set()
        if self._stop_event.is_set():
            return True

        sleep_task = asyncio.create_task(self._sleep(delay_s))
        stop_task = asyncio.create_task(self._stop_event.wait())
        try:
            done, pending = await asyncio.wait(
                {sleep_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done and self._stop_event.is_set():
                return True
            await sleep_task
            return False
        finally:
            for task in (sleep_task, stop_task):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    def _emit_event(self, rec: EventRecord, app_state) -> None:
        try:
            app_state.bus.emit(FleetEvent.model_validate(rec.event))
        except Exception:
            logger.exception("Failed to emit replayed event")

    def _apply_mutation(self, rec: MutationRecord) -> None:
        from api.server.state import app_state

        try:
            if rec.kind == "workflow" and rec.op == "upsert":
                from api.shared.types import Workflow

                app_state.store.upsert_workflow(Workflow.model_validate(rec.patch))
            elif rec.kind == "exception" and rec.op == "upsert":
                from api.shared.types import Exception_ as ExceptionModel

                app_state.store.upsert_exception(ExceptionModel.model_validate(rec.patch))
            else:
                logger.debug("Skipping replay mutation kind=%s op=%s id=%s", rec.kind, rec.op, rec.id)
        except Exception:
            logger.exception("Failed to apply replayed mutation")

    def _emit_restart_pending(self, app_state) -> None:
        app_state.bus.emit(
            FleetEvent(
                type="playback.restart.pending",
                tape_id=self.meta.tape_id,
                duration_s=self.meta.duration_s,
            )
        )

    def current_t(self) -> float:
        if self._cycle_started_at <= 0:
            return self._current_t
        return min(
            self.meta.duration_s,
            max(self._current_t, self._clock() - self._cycle_started_at),
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except asyncio.TimeoutError:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        finally:
            self._task = None


_active_player: Player | None = None


def set_active_player(p: Player | None) -> None:
    global _active_player
    _active_player = p


def current_player() -> Player | None:
    return _active_player
