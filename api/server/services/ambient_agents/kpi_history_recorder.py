"""Per-minute KPI history recorder (pitch-j1 / pitch-j2).

Ambient agent that snapshots agency KPIs (J1) and per-persona load
metrics (J2) into the durable ``kpi_history`` store every
``DEFAULT_TICK_SECONDS`` seconds.

Per-persona load samples are namespaced by ``role`` via the ``dim``
column:

  * ``persona_queue_depth`` — count of workflows currently parked at
    a HITL gate attributed to that role.
  * ``persona_decisions_per_min`` — count of decisions stamped onto
    workflow.payload['decisions'] within the trailing 60 seconds.

Each helper is invoked individually and any exception is swallowed +
logged so a single bad metric cannot halt the loop.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable

from api.server.services import kpi_history

log = logging.getLogger(__name__)


DEFAULT_TICK_SECONDS: float = 60.0

# Agency KPI ids whose helpers in routes.kpis return numeric-coercible
# values. (gross_profit_per_brand returns a list, so it's omitted; the
# others either return a float or None.)
TRACKED_AGENCY_KPIS: tuple[str, ...] = (
    "win_rate_pct",
    "billable_utilisation_pct",
    "client_churn_30d",
    "time_to_launch_days",
    "freelancer_mix_pct",
    "intercompany_recharge_volume",
    "pitch_cost",
)


def _default_agency_kpi_provider() -> dict[str, float]:
    """Read tracked agency KPIs straight off the route helpers."""
    from api.server.routes import kpis as _kpis

    out: dict[str, float] = {}
    for kpi_id in TRACKED_AGENCY_KPIS:
        helper = getattr(_kpis, f"_{kpi_id}", None)
        if helper is None:
            continue
        try:
            value, _reason = helper()
        except Exception:
            log.exception("kpi_history_recorder: helper %s raised", kpi_id)
            continue
        if value is None:
            continue
        try:
            out[kpi_id] = float(value)
        except (TypeError, ValueError):
            continue
    return out


AgencyKpiProvider = Callable[[], dict[str, float]]
PersonaLoadProvider = Callable[[], tuple[dict[str, float], dict[str, float]]]


def _default_persona_load_provider() -> tuple[dict[str, float], dict[str, float]]:
    """Return ``(queue_depth_by_role, decisions_per_min_by_role)``.

    Reads straight off the in-memory workflow store. Lazy-imports
    ``app_state`` so this module stays cheap to import in tests that
    don't wire up the full app.
    """
    queue: dict[str, int] = defaultdict(int)
    decisions: dict[str, int] = defaultdict(int)
    try:
        from api.server.state import app_state
    except Exception:
        return {}, {}
    try:
        from api.shared.domains import DOMAINS
        domains_by_type = DOMAINS if isinstance(DOMAINS, dict) else {}
    except Exception:
        domains_by_type = {}
    cutoff = time.time() - 60.0
    try:
        wfs = list(app_state.store.list_workflows())
    except Exception:
        return {}, {}

    for w in wfs:
        payload = w.payload if isinstance(w.payload, dict) else {}

        if w.status == "awaiting_hitl":
            ctx = payload.get("hitl_context") or {}
            persona_role = ctx.get("persona") or payload.get("persona")
            if not persona_role:
                domain = domains_by_type.get(w.type)
                gates = (
                    getattr(domain, "hitl_gates", None) or [] if domain else []
                )
                for gate in gates:
                    if getattr(gate, "gate_phase", None) == w.current_phase:
                        persona_role = (
                            getattr(gate, "persona", None)
                            or getattr(gate, "persona_role", None)
                        )
                        if persona_role:
                            break
                if not persona_role:
                    for gate in gates:
                        cand = (
                            getattr(gate, "persona", None)
                            or getattr(gate, "persona_role", None)
                        )
                        if cand:
                            persona_role = cand
                            break
            if persona_role:
                queue[str(persona_role)] += 1

        for d in payload.get("decisions") or []:
            role = d.get("persona_role")
            if not role:
                continue
            ts_iso = d.get("decided_at")
            try:
                import datetime as _dt
                if isinstance(ts_iso, str):
                    ts_val = _dt.datetime.fromisoformat(ts_iso).timestamp()
                else:
                    ts_val = float(ts_iso or 0.0)
            except Exception:
                ts_val = 0.0
            if ts_val >= cutoff:
                decisions[str(role)] += 1

    return (
        {role: float(n) for role, n in queue.items()},
        {role: float(n) for role, n in decisions.items()},
    )


class KpiHistoryRecorder:
    """Per-minute snapshotter into the durable ``kpi_history`` store."""

    def __init__(
        self,
        *,
        agency_kpi_provider: AgencyKpiProvider | None = None,
        persona_load_provider: PersonaLoadProvider | None = None,
        tick_seconds: float = DEFAULT_TICK_SECONDS,
    ) -> None:
        self._agency_kpi_provider = (
            agency_kpi_provider or _default_agency_kpi_provider
        )
        self._persona_load_provider = (
            persona_load_provider or _default_persona_load_provider
        )
        self._tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None

    async def tick(self) -> dict[str, int]:
        """Run one snapshot pass.

        Returns per-family counts of samples actually persisted —
        useful for assertions in tests."""
        counts = {"agency": 0, "persona_queue": 0, "persona_decisions": 0}

        try:
            agency = self._agency_kpi_provider()
        except Exception:
            log.exception("kpi_history_recorder: agency_kpi_provider raised")
            agency = {}
        for kpi_id, value in agency.items():
            try:
                kpi_history.record(kpi_id, value)
                counts["agency"] += 1
            except Exception:
                log.exception("kpi_history_recorder: record %s failed", kpi_id)

        try:
            queue_by_role, decisions_by_role = self._persona_load_provider()
        except Exception:
            log.exception("kpi_history_recorder: persona_load_provider raised")
            queue_by_role, decisions_by_role = {}, {}
        for role, depth in queue_by_role.items():
            try:
                kpi_history.record(
                    "persona_queue_depth", float(depth), dim=str(role)
                )
                counts["persona_queue"] += 1
            except Exception:
                log.exception(
                    "kpi_history_recorder: persona_queue_depth %s failed", role
                )
        for role, n in decisions_by_role.items():
            try:
                kpi_history.record(
                    "persona_decisions_per_min", float(n), dim=str(role)
                )
                counts["persona_decisions"] += 1
            except Exception:
                log.exception(
                    "kpi_history_recorder: persona_decisions_per_min %s failed",
                    role,
                )

        return counts

    def start(self) -> None:
        """Schedule the per-minute tick loop on the running event loop.

        Idempotent — re-start cancels the previous task so uvicorn
        --reload cycles don't accumulate loops."""
        self.stop()
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
                log.exception("kpi_history_recorder: tick crashed (swallowed)")
            try:
                await asyncio.sleep(self._tick_seconds)
            except asyncio.CancelledError:
                raise


# Module-level singleton wired by api.server.main lifespan.
_RECORDER = KpiHistoryRecorder()


def start() -> None:
    """Wire the singleton recorder and start its tick loop."""
    _RECORDER.start()


def stop() -> None:
    """Cancel the singleton recorder's tick loop."""
    _RECORDER.stop()
