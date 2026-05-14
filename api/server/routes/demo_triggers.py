"""Demo trigger routes — autonomous-domain-insights v1.1 Phase A4.

Operator-driven HTTP routes that inject realistic state changes for the
demo flow. Three endpoints, all under ``/api/demo/trigger``:

  POST /api/demo/trigger/brand-overrun       (generic)
  POST /api/demo/trigger/in-flight-invoices  (per-brand)
  POST /api/demo/trigger/aurora-overrun      (convenience wrapper)

The first inserts ~5 fresh ``Money`` rows so a freshly-loaded graph can
produce overrun observations on the next CFO summary tick. The second
spawns a few ``ap-invoice`` workflows so the freeze policy has live
work to auto-escalate (the prestige moment). The third is a one-shot
wrapper around (a) + (b) targeting ``BRAND-aurora``.

Generalised from §8.1 of the v1 spec
``docs/superpowers/specs/2026-05-12-autonomous-domain-insights-design.md``.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from api.server.services.entity_graph import EntityWrite
from api.server.services.read_route_auth import Actor, require_actor
from api.server.state import app_state

router = APIRouter(prefix="/api/demo/trigger")


def _pick_top_spend_brand() -> str | None:
    """Return the brand id with the highest current Money spend, or None.

    Falls back to any brand if no Money rows exist yet.
    """
    rows = app_state.entities.query(
        "MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand) "
        "RETURN b.id AS bid, sum(m.amount) AS s "
        "ORDER BY s DESC LIMIT 1"
    )
    if rows and rows[0].get("bid"):
        return str(rows[0]["bid"])
    fallback = app_state.entities.query(
        "MATCH (b:Brand) RETURN b.id AS bid LIMIT 1"
    )
    if fallback and fallback[0].get("bid"):
        return str(fallback[0]["bid"])
    return None


def _pick_account_id() -> str | None:
    rows = app_state.entities.query(
        "MATCH (a:Account) RETURN a.id AS aid LIMIT 1"
    )
    if rows and rows[0].get("aid"):
        return str(rows[0]["aid"])
    return None


def _pick_period_id() -> str | None:
    """Pick the most recent quarter Period; fall back to any Period."""
    rows = app_state.entities.query(
        "MATCH (p:Period) WHERE p.kind = 'quarter' "
        "RETURN p.id AS pid ORDER BY p.`starts` DESC LIMIT 1"
    )
    if rows and rows[0].get("pid"):
        return str(rows[0]["pid"])
    fallback = app_state.entities.query(
        "MATCH (p:Period) RETURN p.id AS pid LIMIT 1"
    )
    if fallback and fallback[0].get("pid"):
        return str(fallback[0]["pid"])
    return None


def _brand_spend_total(brand_id: str) -> float:
    rows = app_state.entities.query(
        "MATCH (m:Money)-[:COSTED_TO_BRAND]->(b:Brand) "
        "WHERE b.id = $bid RETURN sum(m.amount) AS s",
        {"bid": brand_id},
    )
    if not rows:
        return 0.0
    s = rows[0].get("s")
    return float(s) if s is not None else 0.0


def _brand_record(brand_id: str) -> dict[str, Any] | None:
    rows = app_state.entities.query(
        "MATCH (b:Brand) WHERE b.id = $bid "
        "RETURN b.id AS id, b.name AS name, "
        "       b.annual_budget_gbp AS annual_budget_gbp",
        {"bid": brand_id},
    )
    return rows[0] if rows else None


def _do_brand_overrun(brand_id: str | None, target_pct: float) -> dict[str, Any]:
    """Shared implementation for the brand-overrun trigger."""
    if not brand_id:
        brand_id = _pick_top_spend_brand()
    if not brand_id:
        raise HTTPException(status_code=404, detail="no Brand found in graph")

    brand = _brand_record(brand_id)
    if brand is None:
        raise HTTPException(
            status_code=404, detail=f"brand {brand_id!r} not found"
        )
    annual_budget = brand.get("annual_budget_gbp")
    if annual_budget is None or float(annual_budget) <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"brand {brand_id!r} has no annual_budget_gbp",
        )
    annual_budget = float(annual_budget)
    brand_name = str(brand.get("name") or brand_id)

    current_spend = _brand_spend_total(brand_id)
    before_pct = current_spend / annual_budget if annual_budget else 0.0
    target_amount = annual_budget * target_pct
    gap = target_amount - current_spend

    if gap <= 0:
        return {
            "brand_id": brand_id,
            "brand_name": brand_name,
            "before_pct": round(before_pct, 4),
            "after_pct": round(before_pct, 4),
            "money_ids": [],
            "gap_filled_gbp": 0.0,
            "message": (
                f"brand already at {before_pct * 100:.1f}% — no insertion needed "
                f"(target was {target_pct * 100:.1f}%)"
            ),
        }

    account_id = _pick_account_id()
    period_id = _pick_period_id()

    n_rows = 5
    per_row = round(gap / n_rows, 2)
    money_ids: list[str] = []
    short_brand = brand_id.replace("BRAND-", "").lower() or "brand"
    now = datetime.utcnow()

    for i in range(n_rows):
        # Last row absorbs rounding drift so the inserted total exactly
        # matches `gap`.
        amount = per_row if i < n_rows - 1 else round(gap - per_row * (n_rows - 1), 2)
        mid = f"MONEY-DEMO-{short_brand}-{uuid.uuid4().hex[:10]}"
        app_state.entities.upsert(EntityWrite(
            kind="Money",
            id=mid,
            attrs={
                "kind": "po",
                "amount": float(amount),
                "currency": "GBP",
                "attributes": "{}",
            },
            source_workflows=("demo-trigger",),
        ))
        app_state.entities.link(
            mid, "COSTED_TO_BRAND", brand_id, posted_at=now
        )
        if account_id:
            app_state.entities.link(
                mid, "BOOKED_AGAINST", account_id, posted_at=now
            )
        if period_id:
            app_state.entities.link(mid, "BELONGS_TO", period_id)
        money_ids.append(mid)

    new_spend = _brand_spend_total(brand_id)
    after_pct = new_spend / annual_budget if annual_budget else 0.0

    return {
        "brand_id": brand_id,
        "brand_name": brand_name,
        "before_pct": round(before_pct, 4),
        "after_pct": round(after_pct, 4),
        "money_ids": money_ids,
        "gap_filled_gbp": round(gap, 2),
    }


def _spawn_ap_invoice(brand_id: str, idx: int) -> str:
    """Emit a ``workflow.spawn.requested`` FleetEvent for an ap-invoice.

    Mirrors the ``_spawn_policy_set`` helper in
    :mod:`api.server.services.policy_application` — there is no direct
    in-process spawner that accepts a free-form payload, so we publish on
    the bus and let the durable-functions wiring pick it up. Tests
    monkeypatch ``app_state.bus.emit`` to assert the call.
    """
    from api.shared.events import FleetEvent

    workflow_id = f"WF-AP-DEMO-{uuid.uuid4().hex[:12]}"
    invoice_id = f"INV-DEMO-{uuid.uuid4().hex[:8]}"
    payload = {
        "invoice": {
            "invoice_id": invoice_id,
            "brand_id": brand_id,
            "amount_gbp": 5000,
            "vendor_name": f"Demo Vendor {idx}",
            "currency": "GBP",
            "po_id": f"PO-DEMO-{idx}",
            "category": "demo",
        }
    }
    app_state.bus.emit(FleetEvent(
        type="workflow.spawn.requested",
        workflow_id=workflow_id,
        payload={"workflow_type": "ap-invoice", "payload": payload},
    ))
    return workflow_id


def _simulate_ap_invoice_decision_cascade(
    workflow_id: str, brand_id: str, invoice_id: str, amount_gbp: float,
) -> list[dict[str, Any]]:
    """Run the ap_clerk → controller → cfo decision cascade synchronously.

    Each level: invoke the persona's compiled decision_policy with a
    synthesized context (mirroring what an ap-invoice gate would carry),
    record the resulting Decision in the graph, and stop the cascade
    when a non-escalate verdict is reached. Returns the list of recorded
    decision summaries for the response payload.

    This bridges the gap between the bus-emit shim (no in-process
    workflow runtime) and the visible auto-escalation demo: when an
    invoice on a frozen Brand is "spawned", the active freeze is
    detected immediately and Decision rows show in the ticker.
    """
    from datetime import datetime

    from api.server.services import persona_responder as pr

    cascade_chain = ("ap_clerk", "controller", "cfo")
    context = {
        "invoice": {
            "invoice_id": invoice_id,
            "brand_id": brand_id,
            "amount_gbp": amount_gbp,
        },
        "brand_id": brand_id,
        "workflow_id": workflow_id,
        "action": "ap_invoice_processing",
    }
    out: list[dict[str, Any]] = []
    now = datetime.utcnow()
    for role in cascade_chain:
        persona = pr.PERSONA_DEFINITIONS.get(role)
        if persona is None or not callable(persona.decide):
            break
        try:
            result = persona.decide(context)
        except Exception:  # pragma: no cover — defensive
            break
        decision = str(result.get("decision") or "")
        reason = str(result.get("reason") or "")
        phase = "ap_clerk_signoff" if role == "ap_clerk" else (
            "controller_signoff" if role == "controller" else "cfo_signoff"
        )
        try:
            app_state.entities.record_decision(
                workflow_id=workflow_id,
                phase=phase,
                persona_role=role,
                verdict=decision,
                reason=reason,
                decided_at=now,
                source_event="demo.in_flight_invoice",
                attributes={"brand_id": brand_id, "amount_gbp": amount_gbp},
                decided_on=(brand_id,),
            )
        except Exception:  # pragma: no cover — defensive
            pass
        out.append({"role": role, "verdict": decision, "reason": reason[:80]})
        if decision != "escalate":
            break
    return out


def _do_in_flight_invoices(brand_id: str, count: int) -> dict[str, Any]:
    if not brand_id:
        raise HTTPException(status_code=400, detail="brand_id is required")
    if count <= 0:
        raise HTTPException(status_code=400, detail="count must be > 0")
    spawned = []
    cascades = []
    for i in range(count):
        wf_id = _spawn_ap_invoice(brand_id, i + 1)
        spawned.append(wf_id)
        # Demo prestige moment: synchronously run the ap_clerk → controller
        # → cfo cascade so the policy honour Decisions land immediately and
        # show up in the ticker (no real durable orchestrator wired).
        invoice_id = f"INV-DEMO-{wf_id[-12:]}"
        cascades.append({
            "workflow_id": wf_id,
            "decisions": _simulate_ap_invoice_decision_cascade(
                wf_id, brand_id, invoice_id, 5000.0,
            ),
        })
    return {
        "brand_id": brand_id,
        "spawned_workflow_ids": spawned,
        "count": len(spawned),
        "cascades": cascades,
    }


@router.post("/brand-overrun")
async def trigger_brand_overrun(
    brand_id: str | None = Query(default=None),
    target_pct: float = Query(default=0.95, gt=0.0, le=2.0),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    return _do_brand_overrun(brand_id, target_pct)


@router.post("/in-flight-invoices")
async def trigger_in_flight_invoices(
    brand_id: str = Query(..., min_length=1, max_length=128),
    count: int = Query(default=3, ge=1, le=50),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    return _do_in_flight_invoices(brand_id, count)


@router.post("/aurora-overrun")
async def trigger_aurora_overrun(
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Convenience wrapper: brand-overrun + in-flight-invoices on Aurora."""
    brand_id = "BRAND-aurora"
    overrun = _do_brand_overrun(brand_id, 0.95)
    invoices = _do_in_flight_invoices(brand_id, 3)
    return {
        "brand_id": brand_id,
        "brand_name": overrun.get("brand_name"),
        "before_pct": overrun.get("before_pct"),
        "after_pct": overrun.get("after_pct"),
        "money_ids": overrun.get("money_ids", []),
        "gap_filled_gbp": overrun.get("gap_filled_gbp", 0.0),
        "spawned_workflow_ids": invoices.get("spawned_workflow_ids", []),
        "count": invoices.get("count", 0),
        "message": overrun.get("message"),
    }


# ---------------------------------------------------------------------------
# Phase H2 extensions: fx-exposure / vendor-concentration / department-attrition
# ---------------------------------------------------------------------------


def _fx_total_notional(pair: str) -> float:
    rows = app_state.entities.query(
        "MATCH (d:Decision) WHERE d.phase = 'treasury_signoff' "
        "AND d.currency_pair = $pair AND d.notional_gbp IS NOT NULL "
        "RETURN sum(d.notional_gbp) AS s",
        {"pair": pair},
    )
    if not rows:
        return 0.0
    s = rows[0].get("s")
    return float(s) if s is not None else 0.0


# Deterministic notional ladder: 5 rows summing to £10.8M, all between
# £1.5M and £3M. Keeps the seed-style math simple and reproducible.
_FX_NOTIONAL_LADDER_GBP: tuple[float, ...] = (
    1_500_000.0,
    1_800_000.0,
    2_100_000.0,
    2_400_000.0,
    3_000_000.0,
)


@router.post("/fx-exposure")
async def trigger_fx_exposure(
    currency_pair: str = Query(default="EUR/GBP", min_length=3, max_length=16),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Insert ~5 fresh treasury-fx Decisions to trip the Treasurer threshold.

    Each Decision is a ``treasury_signoff`` approval on ``currency_pair``
    with ``notional_gbp`` between £1.5M and £3M (deterministic ladder
    summing to £10.8M, comfortably above the Treasurer's £5M-per-pair
    threshold). ``decided_at`` is spread evenly across the last 7 days.

    Each call ADDS five new Decisions (workflow_ids are uuid-suffixed so
    the per-(workflow_id, phase, persona_role) dedupe key in
    :meth:`EntityGraph.record_decision` always misses on first write).
    Multiple calls compound the exposure — that's intentional for demo
    operators who want to over-trip the threshold.
    """
    before_total = _fx_total_notional(currency_pair)
    now = datetime.utcnow()
    decisions_inserted: list[str] = []
    pair_slug = currency_pair.replace("/", "").lower()

    for i, notional in enumerate(_FX_NOTIONAL_LADDER_GBP):
        # Spread decided_at evenly across the last 7 days (i=0 -> ~7d ago,
        # i=4 -> ~today). Stable per-call within a single trigger.
        offset_hours = int(round((len(_FX_NOTIONAL_LADDER_GBP) - 1 - i) * (7 * 24 / max(1, len(_FX_NOTIONAL_LADDER_GBP) - 1))))
        decided_at = now - timedelta(hours=offset_hours)
        wf_id = f"WF-FX-DEMO-{pair_slug}-{uuid.uuid4().hex[:10]}"
        try:
            did = app_state.entities.record_decision(
                workflow_id=wf_id,
                phase="treasury_signoff",
                persona_role="treasurer",
                verdict="approve",
                reason="demo trigger: fx-exposure",
                decided_at=decided_at,
                source_event="demo.trigger.fx_exposure",
                attributes={
                    "currency_pair": currency_pair,
                    "notional_gbp": float(notional),
                },
                decided_on=(),
            )
            decisions_inserted.append(did)
        except Exception as exc:  # defensive: bad schema / wiring
            return {
                "currency_pair": currency_pair,
                "decisions_inserted": decisions_inserted,
                "total_notional_gbp_added": sum(
                    _FX_NOTIONAL_LADDER_GBP[: len(decisions_inserted)]
                ),
                "before_total": before_total,
                "after_total": _fx_total_notional(currency_pair),
                "message": f"partial insertion ({type(exc).__name__}: {exc})",
            }

    after_total = _fx_total_notional(currency_pair)
    return {
        "currency_pair": currency_pair,
        "decisions_inserted": decisions_inserted,
        "total_notional_gbp_added": float(sum(_FX_NOTIONAL_LADDER_GBP)),
        "before_total": before_total,
        "after_total": after_total,
    }


def _pick_largest_vendor() -> dict[str, Any] | None:
    """Return the vendor (Organisation kind=vendor) with the largest current spend.

    Falls back to any vendor if no PAYS rels exist, or to None if there
    are no vendor Organisations at all.
    """
    rows = app_state.entities.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "WHERE o.kind = 'vendor' "
        "RETURN o.id AS id, o.name AS name, sum(m.amount) AS s "
        "ORDER BY s DESC LIMIT 1"
    )
    if rows and rows[0].get("id"):
        return {
            "id": str(rows[0]["id"]),
            "name": str(rows[0].get("name") or rows[0]["id"]),
        }
    fallback = app_state.entities.query(
        "MATCH (o:Organisation) WHERE o.kind = 'vendor' "
        "RETURN o.id AS id, o.name AS name LIMIT 1"
    )
    if fallback and fallback[0].get("id"):
        return {
            "id": str(fallback[0]["id"]),
            "name": str(fallback[0].get("name") or fallback[0]["id"]),
        }
    return None


def _vendor_concentration_pct(vendor_id: str) -> float:
    rows = app_state.entities.query(
        "MATCH (m:Money)-[:PAYS]->(o:Organisation) "
        "WHERE o.kind = 'vendor' "
        "RETURN o.id AS id, sum(m.amount) AS s"
    )
    total = 0.0
    vendor_total = 0.0
    for r in rows:
        s = float(r.get("s") or 0.0)
        total += s
        if str(r.get("id")) == vendor_id:
            vendor_total = s
    if total <= 0:
        return 0.0
    return vendor_total / total


# Deterministic amount ladder: cycles through 5 values in £15-25k.
_VENDOR_AMOUNT_LADDER_GBP: tuple[float, ...] = (
    15_000.0,
    18_000.0,
    20_000.0,
    22_500.0,
    25_000.0,
)


@router.post("/vendor-concentration")
async def trigger_vendor_concentration(
    vendor_id: str | None = Query(default=None),
    count: int = Query(default=50, ge=1, le=500),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Insert ~50 PO Money rows on a vendor to push concentration > 12%."""
    vendor: dict[str, Any] | None
    if vendor_id:
        rows = app_state.entities.query(
            "MATCH (o:Organisation) WHERE o.id = $id AND o.kind = 'vendor' "
            "RETURN o.id AS id, o.name AS name",
            {"id": vendor_id},
        )
        vendor = (
            {"id": str(rows[0]["id"]), "name": str(rows[0].get("name") or rows[0]["id"])}
            if rows
            else None
        )
    else:
        vendor = _pick_largest_vendor()

    if vendor is None:
        return {
            "vendor_id": vendor_id,
            "vendor_name": None,
            "money_inserted": [],
            "total_added_gbp": 0.0,
            "before_concentration_pct": 0.0,
            "after_concentration_pct": 0.0,
            "message": (
                "no vendor Organisation found in graph "
                "(expected Organisation with kind='vendor')"
            ),
        }

    vid = vendor["id"]
    vname = vendor["name"]
    before_pct = _vendor_concentration_pct(vid)

    account_id = _pick_account_id()
    period_id = _pick_period_id()
    now = datetime.utcnow()
    short_vendor = vid.replace("ORG-", "").replace("vendor-", "").lower() or "vendor"

    money_ids: list[str] = []
    total_added = 0.0
    for i in range(count):
        amount = _VENDOR_AMOUNT_LADDER_GBP[i % len(_VENDOR_AMOUNT_LADDER_GBP)]
        mid = f"MONEY-VC-DEMO-{short_vendor}-{uuid.uuid4().hex[:10]}"
        app_state.entities.upsert(EntityWrite(
            kind="Money",
            id=mid,
            attrs={
                "kind": "po",
                "amount": float(amount),
                "currency": "GBP",
                "attributes": "{}",
            },
            source_workflows=("demo-trigger",),
        ))
        app_state.entities.link(mid, "PAYS", vid, posted_at=now)
        if account_id:
            app_state.entities.link(
                mid, "BOOKED_AGAINST", account_id, posted_at=now
            )
        if period_id:
            app_state.entities.link(mid, "BELONGS_TO", period_id)
        money_ids.append(mid)
        total_added += float(amount)

    after_pct = _vendor_concentration_pct(vid)
    return {
        "vendor_id": vid,
        "vendor_name": vname,
        "money_inserted": money_ids,
        "total_added_gbp": round(total_added, 2),
        "before_concentration_pct": round(before_pct, 4),
        "after_concentration_pct": round(after_pct, 4),
    }


def _persons_in_dept(department: str) -> list[dict[str, Any]]:
    return app_state.entities.query(
        "MATCH (p:Person) WHERE p.department = $dept "
        "RETURN p.id AS id, p.name AS name, p.employed_to AS employed_to",
        {"dept": department},
    )


@router.post("/department-attrition")
async def trigger_department_attrition(
    department: str = Query(default="Tech", min_length=1, max_length=64),
    pct: float = Query(default=0.30, gt=0.0, le=1.0),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Mark ~`pct` of currently-employed Persons in `department` as leavers."""
    persons = _persons_in_dept(department)
    total_in_dept = len(persons)
    if total_in_dept == 0:
        return {
            "department": department,
            "leavers_added": [],
            "total_in_dept": 0,
            "attrition_pct_after": 0.0,
            "message": f"no Persons found in department {department!r}",
        }

    active = [p for p in persons if p.get("employed_to") is None]
    if not active:
        # Compute current attrition for visibility.
        already_left = total_in_dept
        return {
            "department": department,
            "leavers_added": [],
            "total_in_dept": total_in_dept,
            "attrition_pct_after": round(already_left / total_in_dept, 4),
            "message": "no currently-employed Persons remain in department",
        }

    target_n = max(1, int(round(len(active) * pct)))
    target_n = min(target_n, len(active))

    # Deterministic selection: sort by id so repeated calls hit the same
    # cohort first (and subsequent calls advance into the next cohort
    # because the previously-marked rows now have employed_to IS NOT NULL).
    active_sorted = sorted(active, key=lambda r: str(r.get("id") or ""))
    cohort = active_sorted[:target_n]

    today = date.today()
    leavers: list[str] = []
    for idx, row in enumerate(cohort):
        pid = str(row["id"])
        # Spread leave dates across the last 30 days (deterministic by index).
        days_ago = (idx * 29 // max(1, target_n - 1)) if target_n > 1 else 0
        when = today - timedelta(days=days_ago)
        try:
            app_state.entities.upsert(EntityWrite(
                kind="Person",
                id=pid,
                attrs={"employed_to": when},
                source_workflows=("demo-trigger",),
            ))
            leavers.append(pid)
        except Exception:
            # Defensive: skip rows whose update fails (e.g. transient
            # schema drift); continue with the rest.
            continue

    refreshed = _persons_in_dept(department)
    left_count = sum(1 for p in refreshed if p.get("employed_to") is not None)
    attrition_pct_after = (
        left_count / len(refreshed) if refreshed else 0.0
    )
    return {
        "department": department,
        "leavers_added": leavers,
        "total_in_dept": len(refreshed),
        "attrition_pct_after": round(attrition_pct_after, 4),
    }


# ---------------------------------------------------------------------------
# v1.2 polish: one-click full Aurora demo arc
# ---------------------------------------------------------------------------


def _latest_cfo_insight() -> dict[str, Any] | None:
    rows = app_state.entities.query(
        "MATCH (i:Insight {role: 'cfo'}) "
        "RETURN i.id AS id, i.role AS role, i.headline AS headline, "
        "       i.body AS body, i.proposed_actions AS proposed_actions, "
        "       i.kpis AS kpis "
        "ORDER BY i.decided_at DESC LIMIT 1"
    )
    if not rows:
        return None
    row = rows[0]
    out: dict[str, Any] = {
        "id": row.get("id"),
        "role": row.get("role"),
        "headline": row.get("headline") or "",
        "body": row.get("body") or "",
    }
    for col in ("proposed_actions", "kpis"):
        raw = row.get(col)
        if raw:
            try:
                out[col] = json.loads(raw)
            except (TypeError, ValueError):
                out[col] = [] if col == "proposed_actions" else {}
        else:
            out[col] = [] if col == "proposed_actions" else {}
    return out


async def _refresh_persona_summary(role: str) -> None:
    """Force an immediate summary tick for `role` (bypass cadence loop)."""
    from api.server.services import persona_responder as pr
    from api.shared.events import FleetEvent

    await pr._handle_summary_request(FleetEvent(
        type="domain.summary.requested",
        payload={"role": role},
    ))


@router.post("/full-aurora-arc")
async def trigger_full_aurora_arc(
    delay_seconds: float = Query(default=0.0, ge=0.0, le=30.0),
    count: int = Query(default=3, ge=1, le=20),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """One-click full demo arc: overrun → CFO observe → freeze → cascade → CEO.

    Synchronous: returns the complete per-phase timeline so the caller
    can reconstruct the narrative on screen. Pacing between phases is
    controlled by ``delay_seconds`` so the operator's eyes (and the
    on-screen ticker) have time to catch up.
    """
    from api.server.services.policy_application import (
        apply_proposed_actions,
        PolicyApplicationOutcome,
    )

    brand_id = "BRAND-aurora"
    phases: list[dict[str, Any]] = []
    arc_started = time.perf_counter()

    async def _pause() -> None:
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    # --- Phase 1: force overrun ---------------------------------------------
    t0 = time.perf_counter()
    overrun = _do_brand_overrun(brand_id, target_pct=1.0)
    phases.append({
        "phase": "overrun",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "summary": overrun,
    })
    await _pause()

    # --- Phase 2: refresh CFO insight, capture observation ------------------
    t0 = time.perf_counter()
    await _refresh_persona_summary("cfo")
    cfo_pre = _latest_cfo_insight() or {}
    phases.append({
        "phase": "cfo_observe",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "headline": cfo_pre.get("headline", ""),
        "proposed_action_count": len(cfo_pre.get("proposed_actions", []) or []),
    })
    await _pause()

    # --- Phase 3: matrix-gated auto-apply -----------------------------------
    # No operator click. The persona's proposed_action goes through the
    # AGT kernel; if the matrix authorises, it's recorded as a Decision.
    t0 = time.perf_counter()
    actions = cfo_pre.get("proposed_actions") or []
    target_action = next(
        (a for a in actions if isinstance(a, dict) and a.get("id") == "freeze-brand-aurora"),
        None,
    )
    workflow_id: str | None = None
    if target_action is not None:
        outcomes = apply_proposed_actions("cfo", [target_action])
        if outcomes and outcomes[0]["outcome"] == PolicyApplicationOutcome.APPLIED:
            workflow_id = outcomes[0]["workflow_id"]
    phases.append({
        "phase": "approve",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "policy_workflow_id": workflow_id,
        "approved_action_id": "freeze-brand-aurora" if target_action else None,
    })
    await _pause()

    # --- Phase 4: refresh CFO again — Aurora drops from proposed_actions ----
    t0 = time.perf_counter()
    await _refresh_persona_summary("cfo")
    cfo_post = _latest_cfo_insight() or {}
    post_actions = cfo_post.get("proposed_actions") or []
    freezes_remaining = sum(
        1 for a in post_actions
        if isinstance(a, dict) and str(a.get("verdict", "")) == "freeze"
    )
    phases.append({
        "phase": "cfo_observe_post",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "headline": cfo_post.get("headline", ""),
        "freezes_remaining": freezes_remaining,
    })
    await _pause()

    # --- Phase 5: spawn in-flight invoices → cascade auto-escalates ---------
    t0 = time.perf_counter()
    invoices = _do_in_flight_invoices(brand_id, count)
    phases.append({
        "phase": "spawn_invoices",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "spawned_workflow_ids": invoices.get("spawned_workflow_ids", []),
        "cascades": invoices.get("cascades", []),
    })
    await _pause()

    # --- Phase 6: refresh CEO synthesis -------------------------------------
    t0 = time.perf_counter()
    await _refresh_persona_summary("ceo")
    ceo_rows = app_state.entities.query(
        "MATCH (i:Insight {role: 'ceo'}) "
        "RETURN i.headline AS headline "
        "ORDER BY i.decided_at DESC LIMIT 1"
    )
    ceo_headline = str(ceo_rows[0].get("headline") or "") if ceo_rows else ""
    phases.append({
        "phase": "ceo_synthesise",
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        "headline": ceo_headline,
    })

    total_elapsed_ms = int((time.perf_counter() - arc_started) * 1000)
    cfo_pct_int = 0
    if cfo_pre.get("headline"):
        try:
            cfo_pct_int = int(round(float(overrun.get("after_pct", 0.0)) * 100))
        except (TypeError, ValueError):
            cfo_pct_int = 0
    narrative = (
        f"Aurora overrun → CFO observed at {cfo_pct_int}% → "
        f"freeze approved → CFO updated to {freezes_remaining} freezes remaining → "
        f"{count} invoices spawned and auto-escalated → CEO synthesis refreshed"
    )

    return {
        "phases": phases,
        "total_elapsed_ms": total_elapsed_ms,
        "narrative": narrative,
    }


# ---------------------------------------------------------------------------
# v1.2: demo state reset (clean re-runs without restarting the stack)
# ---------------------------------------------------------------------------


_DEMO_MONEY_PREFIXES: tuple[str, ...] = (
    "MONEY-DEMO-",
    "MONEY-FX-DEMO-",
    "MONEY-VC-DEMO-",
)
_DEMO_WORKFLOW_PREFIXES: tuple[str, ...] = ("WF-AP-DEMO-",)
_DEMO_DECISION_SOURCE_EVENTS: tuple[str, ...] = (
    "demo.in_flight_invoice",
    "persona.action.approved",
)


def _count(cypher: str, params: dict[str, Any] | None = None) -> int:
    rows = app_state.entities.query(cypher, params or {})
    if not rows:
        return 0
    val = rows[0].get("n")
    try:
        return int(val) if val is not None else 0
    except (TypeError, ValueError):
        return 0


@router.post("/reset")
async def trigger_demo_reset(
    keep_seed: bool = Query(default=True),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Wipe demo-added Money / Workflows / Decisions (and optionally Insights).

    With ``keep_seed=true`` (default) the original seeded graph is left
    untouched: only rows whose ids carry a demo-trigger prefix (or whose
    Decision rows reference a demo source_event) are removed. With
    ``keep_seed=false`` we additionally drop every Insight row.

    All demo-added rels are auto-removed by Kuzu's ``DETACH DELETE``.

    The persona cadence loop will re-publish baseline insights within
    ~15 seconds of the reset returning.
    """
    g = app_state.entities

    money_deleted = 0
    for prefix in _DEMO_MONEY_PREFIXES:
        n = _count(
            "MATCH (m:Money) WHERE m.id STARTS WITH $p RETURN count(m) AS n",
            {"p": prefix},
        )
        if n:
            g.query(
                "MATCH (m:Money) WHERE m.id STARTS WITH $p DETACH DELETE m",
                {"p": prefix},
            )
            money_deleted += n

    workflows_deleted = 0
    for prefix in _DEMO_WORKFLOW_PREFIXES:
        n = _count(
            "MATCH (w:Workflow) WHERE w.id STARTS WITH $p RETURN count(w) AS n",
            {"p": prefix},
        )
        if n:
            g.query(
                "MATCH (w:Workflow) WHERE w.id STARTS WITH $p DETACH DELETE w",
                {"p": prefix},
            )
            workflows_deleted += n

    sources = list(_DEMO_DECISION_SOURCE_EVENTS)
    decisions_deleted = _count(
        "MATCH (d:Decision) WHERE d.source_event IN $s RETURN count(d) AS n",
        {"s": sources},
    )
    if decisions_deleted:
        g.query(
            "MATCH (d:Decision) WHERE d.source_event IN $s DETACH DELETE d",
            {"s": sources},
        )

    insights_deleted = 0
    if not keep_seed:
        insights_deleted = _count(
            "MATCH (i:Insight) RETURN count(i) AS n"
        )
        if insights_deleted:
            g.query("MATCH (i:Insight) DETACH DELETE i")

    # Heuristic: persons whose employed_to is within the last hour are
    # the ones the department-attrition trigger just marked as leavers
    # (real seeded leavers carry historical dates).
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_rows = g.query(
        "MATCH (p:Person) "
        "WHERE p.employed_to IS NOT NULL AND p.employed_to >= $cutoff "
        "RETURN p.id AS id",
        {"cutoff": one_hour_ago.date()},
    )
    persons_unattrited = 0
    for row in recent_rows or ():
        pid = row.get("id")
        if not pid:
            continue
        try:
            g.query(
                "MATCH (p:Person) WHERE p.id = $id SET p.employed_to = NULL",
                {"id": str(pid)},
            )
            persons_unattrited += 1
        except Exception:
            continue

    return {
        "rows_deleted": {
            "money": money_deleted,
            "workflows": workflows_deleted,
            "decisions": decisions_deleted,
            "insights": insights_deleted,
            "persons_unattrited": persons_unattrited,
        },
        "kept_seed": bool(keep_seed),
        "message": (
            "Demo state reset. The cadence loop will re-publish persona "
            "insights within 15 seconds."
        ),
    }
