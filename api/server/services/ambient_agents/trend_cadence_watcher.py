"""KPI-trend-driven cadence triggers (pitch-i5).

Ambient agent that watches *trends* (slopes) in agency KPIs rather
than instantaneous snapshots. Every minute it:

    1. Computes current values for the agency KPIs (re-using the
       ``api.server.routes.kpis`` helpers — direct call, no HTTP).
    2. Records each into the provisional ``kpi_trend_buffer``.
    3. Computes the slope over the last 7 minutes (per pitch-c5 the
       demo time-compresses 7 wall-minutes into 7 business-days).
    4. For each ``TREND_RULES`` entry that fires, spawns the matching
       workflow_type ONCE per ``(kpi, hour_of_day)`` so a sustained
       multi-tick trend doesn't carpet-bomb the queue.

The watcher is intentionally injectable on every collaborator
(KPI provider, spawn function, hour clock) so the unit tests can
drive deterministic synthetic series without touching the entity
graph or the Functions host.

Defensive: every per-KPI step is wrapped in try/except + log so a
single broken KPI helper can never halt the loop.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import logging
from typing import Awaitable, Callable

from api.server.services import kpi_trend_buffer
from api.shared.events import FleetEvent

log = logging.getLogger(__name__)


# (kpi_id, direction, threshold_per_minute, workflow_type)
# direction:
#   "down" — fire when slope_per_minute <= threshold (threshold is negative)
#   "up"   — fire when slope_per_minute >= threshold (threshold is positive)
TREND_RULES: tuple[tuple[str, str, float, str], ...] = (
    ("win_rate_pct",                "down", -1.0,      "new-business-pipeline-scrub"),
    ("billable_utilisation_pct",    "up",    1.0,      "talent-redeployment"),
    ("intercompany_recharge_volume","up",    50_000.0, "monthly-client-pnl"),
    ("client_churn_30d",            "up",    0.5,      "client-renewal"),
)

# 7 wall-minutes ↔ 7 business-days per pitch-c5's time compression.
DEFAULT_SLOPE_WINDOW_SECONDS: int = 7 * 60

# Loop tick interval. One sample per minute keeps the buffer cost
# trivial while still giving the 7-minute slope window 7 datapoints.
DEFAULT_TICK_SECONDS: float = 60.0


KpiProvider = Callable[[], dict[str, float]]
SpawnFn = Callable[[str], Awaitable[object]]
HourProvider = Callable[[], int]


def _default_kpi_provider() -> dict[str, float]:
    """Read the watched KPIs straight off the route helpers.

    We import lazily so this module is cheap to import in tests that
    don't need the full app_state wired up. Any KPI that returns a
    non-numeric value (e.g. the gross-profit-per-brand list, or a KPI
    flagged unavailable) is silently dropped — those are not in
    ``TREND_RULES`` anyway.
    """
    from api.server.routes import kpis as _kpis

    out: dict[str, float] = {}
    for kpi_id, _direction, _threshold, _wt in TREND_RULES:
        helper_name = f"_{kpi_id}"
        helper = getattr(_kpis, helper_name, None)
        if helper is None:
            log.debug("trend_cadence_watcher: no helper %s on routes.kpis", helper_name)
            continue
        try:
            value, _reason = helper()
        except Exception:
            log.exception("trend_cadence_watcher: helper %s raised", helper_name)
            continue
        if value is None:
            continue
        try:
            out[kpi_id] = float(value)
        except (TypeError, ValueError):
            log.debug(
                "trend_cadence_watcher: %s returned non-numeric %r — skipping",
                kpi_id, value,
            )
    return out


async def _default_spawn_fn(workflow_type: str) -> object:
    """Spawn a workflow via the same path the cadence loader uses."""
    from api.server.services.cadence_loader import _default_spawn_workflow
    return await _default_spawn_workflow(workflow_type)


def _default_hour_provider() -> int:
    return _dt.datetime.now(tz=_dt.timezone.utc).hour


def _rule_fires(direction: str, threshold: float, slope_per_minute: float) -> bool:
    if direction == "down":
        return slope_per_minute <= threshold
    if direction == "up":
        return slope_per_minute >= threshold
    log.warning("trend_cadence_watcher: unknown direction %r — ignoring", direction)
    return False


class TrendCadenceWatcher:
    """Computes KPI slopes and spawns trend-driven workflows."""

    def __init__(
        self,
        *,
        bus=None,
        kpi_provider: KpiProvider | None = None,
        spawn_fn: SpawnFn | None = None,
        hour_provider: HourProvider | None = None,
        rules: tuple[tuple[str, str, float, str], ...] = TREND_RULES,
        slope_window_seconds: int = DEFAULT_SLOPE_WINDOW_SECONDS,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        self._bus = bus
        self._kpi_provider = kpi_provider or _default_kpi_provider
        self._spawn_fn = spawn_fn or _default_spawn_fn
        self._hour_provider = hour_provider or _default_hour_provider
        self._rules = rules
        self._slope_window_seconds = slope_window_seconds
        self._tick_seconds = tick_seconds
        # Idempotency ledger: (kpi_id, hour_of_day) → already fired.
        self._seen: set[tuple[str, int]] = set()
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # core tick — directly testable without an event loop
    # ------------------------------------------------------------------

    async def tick(self) -> list[tuple[str, str]]:
        """Run one trend-evaluation pass.

        Returns a list of ``(kpi_id, workflow_type)`` actually spawned
        this tick (after idempotency suppression). Exceptions in any
        single rule are logged + swallowed.
        """
        spawned: list[tuple[str, str]] = []
        try:
            values = self._kpi_provider()
        except Exception:
            log.exception("trend_cadence_watcher: kpi_provider raised — skipping tick")
            return spawned

        for kpi_id, value in values.items():
            try:
                kpi_trend_buffer.record(kpi_id, value)
            except Exception:
                log.exception("trend_cadence_watcher: record failed for %s", kpi_id)

        for kpi_id, direction, threshold, workflow_type in self._rules:
            try:
                slope_per_second = kpi_trend_buffer.slope(
                    kpi_id, self._slope_window_seconds
                )
                if slope_per_second is None:
                    continue
                slope_per_minute = slope_per_second * 60.0
                if not _rule_fires(direction, threshold, slope_per_minute):
                    continue
                key = (kpi_id, self._hour_provider())
                if key in self._seen:
                    log.debug(
                        "trend_cadence_watcher: %s already fired this hour; skipping",
                        kpi_id,
                    )
                    continue
                self._seen.add(key)
                log.info(
                    "[trend_cadence_watcher] %s %s trend (slope=%.2f) — "
                    "spawning %s",
                    kpi_id.upper(), direction, slope_per_minute, workflow_type,
                )
                self._emit_trend_fired(
                    kpi_id, direction, slope_per_minute, threshold, workflow_type,
                )
                await self._safe_spawn(workflow_type)
                spawned.append((kpi_id, workflow_type))
            except Exception:
                log.exception(
                    "trend_cadence_watcher: rule eval failed for %s", kpi_id
                )
        return spawned

    async def _safe_spawn(self, workflow_type: str) -> None:
        try:
            await self._spawn_fn(workflow_type)
        except Exception:
            log.exception(
                "trend_cadence_watcher: spawn_fn raised for %s", workflow_type
            )

    def _emit_trend_fired(
        self,
        kpi_id: str,
        direction: str,
        slope_per_minute: float,
        threshold: float,
        workflow_type: str,
    ) -> None:
        if self._bus is None:
            return
        try:
            self._bus.emit(FleetEvent(
                type="trend.fired",
                kpi_id=kpi_id,
                direction=direction,
                slope_per_minute=slope_per_minute,
                threshold=threshold,
                workflow_type=workflow_type,
            ))
        except Exception:
            log.exception(
                "trend_cadence_watcher: trend.fired emit failed for %s", kpi_id
            )

    # ------------------------------------------------------------------
    # background loop lifecycle
    # ------------------------------------------------------------------

    def start(self, bus=None) -> None:
        """Schedule the per-minute tick loop on the running event loop.

        Idempotent — re-start cancels the previous task so uvicorn
        --reload cycles don't accumulate loops.
        """
        self.stop()
        if bus is not None:
            self._bus = bus
        self._task = asyncio.create_task(self._run_forever())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run_forever(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("trend_cadence_watcher: tick crashed (swallowed)")
            try:
                await asyncio.sleep(self._tick_seconds)
            except asyncio.CancelledError:
                raise


# Module-level singleton wired by api.server.main lifespan.
_WATCHER = TrendCadenceWatcher()


def start(bus=None) -> None:
    """Wire the singleton watcher and start its tick loop."""
    _WATCHER.start(bus=bus)


def stop() -> None:
    """Cancel the singleton watcher's tick loop."""
    _WATCHER.stop()


def _reset_for_tests() -> None:
    """Test-only: clear the per-(kpi, hour) idempotency ledger."""
    _WATCHER._seen.clear()
