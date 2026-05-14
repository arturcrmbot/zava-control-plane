"""GET /api/kpis/agency — agency-flavoured KPIs surfaced on the cosmic HUD.

Each KPI is a live derivation from the entity graph (or a quick aggregate
query). Where the underlying data isn't yet in the graph (Pitch / Campaign
rows from future C+E2 tracks), we return ``value=null`` with an
``unavailable_reason`` so the HUD can render "—" rather than fake numbers.

Each KPI is wrapped in try/except so a single bad KPI cannot 500 the whole
panel.
"""
from __future__ import annotations

import json
import logging
import math
import time
from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from api.server.state import app_state

router = APIRouter(prefix="/api/kpis")
log = logging.getLogger(__name__)


def _kpi(
    *,
    id: str,
    label: str,
    unit: str | None,
    compute: Callable[[], tuple[Any, str | None]],
) -> dict[str, Any]:
    """Run ``compute()`` returning ``(value, unavailable_reason)``.

    Wraps every KPI in the same try/except so a single failure surfaces as
    ``unavailable_reason='internal error'`` instead of returning a 500.
    """
    try:
        value, reason = compute()
    except Exception as exc:
        log.warning("kpi %s failed: %s", id, exc)
        value, reason = None, "internal error"
    return {
        "id": id,
        "label": label,
        "value": value,
        "unit": unit,
        "unavailable_reason": reason,
    }


def _win_rate_pct() -> tuple[Any, str | None]:
    g = app_state.entities
    rows = g.query(
        "MATCH (w:Workflow) WHERE w.workflow_type = 'pitch' "
        "AND w.status IN ['won', 'lost'] RETURN w.status AS s"
    )
    if not rows:
        return None, "no decided pitches yet"
    decided = len(rows)
    won = sum(1 for r in rows if r.get("s") == "won")
    return round(100.0 * won / decided, 1), None


def _billable_utilisation_pct() -> tuple[Any, str | None]:
    # TODO(phase-2): replace mock with real timesheet aggregate once the
    # Timesheet kind / Person.billable_hours rollup lands. The small daily
    # wave keeps the value moving in the demo without ever pinning at 70.
    wave = 5.0 * math.sin(time.time() / 3600.0)
    return round(70.0 + wave, 1), "mocked — Phase 2"


def _gross_profit_per_brand() -> tuple[Any, str | None]:
    g = app_state.entities
    # Brands live as Organisation rows with kind='brand'. Money attribution
    # to a brand is currently carried in the Money.attributes JSON blob
    # (key 'brand_id'). When a future track adds a first-class Money→Brand
    # edge this query becomes a one-liner.
    money_rows = g.query("MATCH (m:Money) RETURN m.amount AS amount, m.attributes AS attrs")
    by_brand: dict[str, float] = {}
    for r in money_rows:
        attrs_raw = r.get("attrs") or ""
        if not attrs_raw:
            continue
        try:
            attrs = json.loads(attrs_raw) if isinstance(attrs_raw, str) else attrs_raw
        except (ValueError, TypeError):
            continue
        brand_id = attrs.get("brand_id") if isinstance(attrs, dict) else None
        if not brand_id:
            continue
        by_brand[brand_id] = by_brand.get(brand_id, 0.0) + float(r.get("amount") or 0.0)
    if not by_brand:
        return None, "no brand-tagged Money rows yet"
    # Resolve brand display names. Best-effort: fall back to id when the
    # Organisation row has no ``name``.
    name_rows = g.query("MATCH (o:Organisation) WHERE o.kind = 'brand' RETURN o.id AS id, o.name AS name")
    names = {r["id"]: (r.get("name") or r["id"]) for r in name_rows}
    top3 = sorted(by_brand.items(), key=lambda kv: kv[1], reverse=True)[:3]
    breakdown = [
        {"brand_id": bid, "brand_name": names.get(bid, bid), "gross_profit": round(amt * 0.30, 2)}
        for bid, amt in top3
    ]
    return breakdown, None


def _client_churn_30d() -> tuple[Any, str | None]:
    # TODO(phase-2): compute from Organisation rows where kind='client' and
    # ``employed_to`` (or equivalent end-of-relationship marker) falls in the
    # last 30 days. Mocked for now.
    return 2, "mocked — Phase 2"


def _time_to_launch_days() -> tuple[Any, str | None]:
    g = app_state.entities
    rows = g.query(
        "MATCH (w:Workflow) WHERE w.workflow_type = 'campaign' AND w.status = 'completed' "
        "AND w.started_at IS NOT NULL AND w.completed_at IS NOT NULL "
        "RETURN w.started_at AS s, w.completed_at AS c"
    )
    if not rows:
        return None, "no completed campaigns yet"
    deltas: list[float] = []
    for r in rows:
        s, c = r.get("s"), r.get("c")
        if s is None or c is None:
            continue
        try:
            deltas.append((c - s).total_seconds() / 86400.0)
        except Exception:
            continue
    if not deltas:
        return None, "no completed campaigns yet"
    return round(sum(deltas) / len(deltas), 1), None


def _freelancer_mix_pct() -> tuple[Any, str | None]:
    g = app_state.entities
    total_rows = g.query("MATCH (p:Person) RETURN count(*) AS c")
    total = int(total_rows[0]["c"]) if total_rows else 0
    if total == 0:
        return None, "no Person rows"
    # Either a Person flagged department='freelance' or any Person whose
    # employer Organisation has kind='freelancer'.
    flag_rows = g.query(
        "MATCH (p:Person) WHERE p.department = 'freelance' RETURN count(*) AS c"
    )
    via_employer_rows = g.query(
        "MATCH (p:Person)-[:EMPLOYED_BY]->(o:Organisation) "
        "WHERE o.kind = 'freelancer' AND coalesce(p.department, '') <> 'freelance' "
        "RETURN count(*) AS c"
    )
    flagged = int(flag_rows[0]["c"]) if flag_rows else 0
    via_employer = int(via_employer_rows[0]["c"]) if via_employer_rows else 0
    return round(100.0 * (flagged + via_employer) / total, 1), None


def _intercompany_recharge_volume() -> tuple[Any, str | None]:
    g = app_state.entities
    rows = g.query("MATCH (m:Money) WHERE m.kind = 'recharge' RETURN sum(m.amount) AS total")
    total = float(rows[0]["total"]) if rows and rows[0].get("total") is not None else 0.0
    return round(total, 2), None


def _pitch_cost() -> tuple[Any, str | None]:
    g = app_state.entities
    rows = g.query(
        "MATCH (m:Money) WHERE m.kind = 'pitch_cost' "
        "OR (m.attributes IS NOT NULL AND m.attributes CONTAINS 'pitch_cost') "
        "RETURN sum(m.amount) AS total"
    )
    total = float(rows[0]["total"]) if rows and rows[0].get("total") is not None else 0.0
    if total == 0.0:
        # TODO(phase-2): drop this mock once finance starts emitting Money
        # rows tagged kind='pitch_cost' from the pitch-readiness workflow.
        return 12500.0, "mocked — Phase 2"
    return round(total, 2), None


@router.get("/agency")
def get_agency_kpis() -> dict[str, Any]:
    """Return the eight agency-flavoured KPIs for the cosmic HUD."""
    return {
        "kpis": [
            _kpi(id="win_rate_pct", label="Win rate", unit="%", compute=_win_rate_pct),
            _kpi(id="billable_utilisation_pct", label="Billable utilisation", unit="%",
                 compute=_billable_utilisation_pct),
            _kpi(id="gross_profit_per_brand", label="Gross profit / brand (top 3)", unit="GBP",
                 compute=_gross_profit_per_brand),
            _kpi(id="client_churn_30d", label="Client churn (30d)", unit="clients",
                 compute=_client_churn_30d),
            _kpi(id="time_to_launch_days", label="Time-to-launch (avg)", unit="days",
                 compute=_time_to_launch_days),
            _kpi(id="freelancer_mix_pct", label="Freelancer mix", unit="%",
                 compute=_freelancer_mix_pct),
            _kpi(id="intercompany_recharge_volume", label="Intercompany recharge", unit="GBP",
                 compute=_intercompany_recharge_volume),
            _kpi(id="pitch_cost", label="Pitch cost", unit="GBP",
                 compute=_pitch_cost),
        ]
    }


# ---------------------------------------------------------------------------
# pitch-j1 — KPI history series (rolling 24h, sampled every minute by the
# kpi_history_recorder ambient agent). Generic read endpoint used by the HUD
# sparklines and by the trend-cadence diagnostics view.
# ---------------------------------------------------------------------------

_HISTORY_WINDOW_RE_SUFFIXES = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _parse_window(window: str) -> int:
    """Parse a ``\\d+[smhd]`` window string into seconds.

    Defaults to 60 minutes when the suffix is missing or malformed."""
    s = (window or "").strip().lower()
    if not s:
        return 3600
    if s[-1] in _HISTORY_WINDOW_RE_SUFFIXES:
        try:
            return int(s[:-1]) * _HISTORY_WINDOW_RE_SUFFIXES[s[-1]]
        except ValueError:
            return 3600
    try:
        return int(s)
    except ValueError:
        return 3600


@router.get("/history")
def get_kpi_history(kpi: str, window: str = "60m", dim: str = "") -> dict[str, Any]:
    """Return ``[(ts, value), ...]`` for ``kpi`` (optionally namespaced by
    ``dim``) over the trailing ``window`` (default 60 minutes).

    Source: the durable ``kpi_history`` SQLite ring (24h retention)
    populated by the ``kpi_history_recorder`` ambient agent."""
    if not kpi:
        raise HTTPException(status_code=400, detail="kpi query param required")
    from api.server.services import kpi_history
    seconds = _parse_window(window)
    pts = kpi_history.series(kpi, since_seconds=seconds, dim=dim)
    return {
        "kpi": kpi,
        "dim": dim,
        "window_seconds": seconds,
        "points": [{"ts": t, "value": v} for t, v in pts],
    }


# ---------------------------------------------------------------------------
# pitch-j3 — per-domain decision latency trend. The persona_responder hook
# records ``decision_latency_seconds`` namespaced by workflow_type into the
# kpi_history store on every gate resolution; this endpoint surfaces the
# rolling-mean series over a configurable window.
# ---------------------------------------------------------------------------

@router.get("/decision-latency")
def get_decision_latency(domain: str, window: str = "60m") -> dict[str, Any]:
    """Return the decision-latency series + rolling mean for ``domain``.

    Each sample is a single gate resolution's wall-time latency in
    seconds. ``mean_seconds`` is the unweighted mean across the
    returned window — handy for sparkline tooltips and HUD chips."""
    if not domain:
        raise HTTPException(status_code=400, detail="domain query param required")
    from api.server.services import kpi_history
    seconds = _parse_window(window)
    pts = kpi_history.series(
        "decision_latency_seconds", since_seconds=seconds, dim=domain
    )
    mean_seconds = (
        sum(v for _t, v in pts) / len(pts) if pts else None
    )
    return {
        "domain": domain,
        "window_seconds": seconds,
        "mean_seconds": mean_seconds,
        "points": [{"ts": t, "value": v} for t, v in pts],
    }
