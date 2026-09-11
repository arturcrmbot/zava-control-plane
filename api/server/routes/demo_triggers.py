"""Demo trigger routes — autonomous-domain-insights v1.1 Phase A4.

Operator-driven HTTP routes that inject realistic state changes for the
demo flow. Three endpoints, all under ``/api/demo/trigger``:

  POST /api/demo/trigger/brand-overrun       (generic)
  POST /api/demo/trigger/in-flight-invoices  (per-brand)
  POST /api/demo/trigger/aurora-overrun      (convenience wrapper)

The first inserts ~5 fresh ``Money`` rows so a freshly-loaded graph can
produce overrun observations on the next CFO summary tick. The legacy-named
``in-flight-invoices`` route now queues real ``FleetApInvoiceOrchestrator``
instances and reports them as queued. The Aurora flagship route starts the
asynchronous ``AuroraBudgetResponseOrchestrator``; it does not apply policy or
manufacture decisions inside the request.

Generalised from §8.1 of the v1 spec
``docs/superpowers/specs/2026-05-12-autonomous-domain-insights-design.md``.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from api.server.services.entity_graph import EntityWrite
from api.server.services.read_route_auth import Actor, require_actor
from api.server.state import app_state
from api.shared.types import Workflow

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


async def _do_in_flight_invoices(brand_id: str, count: int) -> dict[str, Any]:
    if not brand_id:
        raise HTTPException(status_code=400, detail="brand_id is required")
    if count <= 0:
        raise HTTPException(status_code=400, detail="count must be > 0")
    from api.server.mcp_tools.invoice_repository import get_invoice
    from api.server.services.durable_client import schedule_new_orchestration

    spawned = []
    for i in range(count):
        token = uuid.uuid4().hex[:12].upper()
        workflow_id = f"API-{token}"
        instance_id = f"ap-demo-{token.lower()}"
        invoice_id = f"INV-DEMO-{token[:8]}"
        record = get_invoice(invoice_id)
        invoice = {
            **record,
            "vendor_name": record["vendor"],
            "brand_id": brand_id,
            "po_id": f"PO-DEMO-{token[:8]}",
            "category": record["gl_category"],
            "scenario": "matched-clean",
        }
        payload = {
            "workflow_id": workflow_id,
            "type": "ap-invoice",
            "invoice": invoice,
            "scenario": "matched-clean",
        }
        try:
            durable = await schedule_new_orchestration(
                payload,
                function_name="FleetApInvoiceOrchestrator",
                instance_id=instance_id,
            )
        except Exception as exc:
            raise HTTPException(
                503,
                {
                    "message": (
                        f"AP batch incomplete: {len(spawned)} of {count} starts confirmed; "
                        f"item {i + 1} could not be confirmed. Inspect the returned IDs before retrying."
                    ),
                    "started_workflow_ids": list(spawned),
                    "unconfirmed_workflow_id": workflow_id,
                    "unconfirmed_instance_id": instance_id,
                    "requested_count": count,
                    "failed_item": i + 1,
                },
            ) from exc
        workflow = app_state.store.get_workflow(workflow_id)
        if workflow is None:
            now = time.time()
            workflow = Workflow(
                id=workflow_id,
                type="ap-invoice",
                status="in_progress",
                current_phase="Invoice Lookup",
                created_at=now,
                sla_due_at=now + 86400,
                jurisdiction="London-Zava",
                agency="Zava",
                orchestration_instance_id=durable.get("id") or instance_id,
                payload={"invoice": invoice, "scenario": "matched-clean"},
            )
            app_state.store.upsert_workflow(workflow)
        spawned.append(workflow_id)
    return {
        "brand_id": brand_id,
        "spawned_workflow_ids": spawned,
        "count": len(spawned),
        "queue_status": "queued",
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
    return await _do_in_flight_invoices(brand_id, count)


@router.post("/aurora-overrun")
async def trigger_aurora_overrun(
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Legacy convenience wrapper: brand overrun plus queued AP workflows."""
    brand_id = "BRAND-aurora"
    overrun = _do_brand_overrun(brand_id, 0.95)
    invoices = await _do_in_flight_invoices(brand_id, 3)
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


def _aurora_request_ids(request_id: str) -> tuple[str, str]:
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:16]
    return f"AUR-{digest.upper()}", f"aurora-{digest}"


@router.post("/full-aurora-arc", status_code=202)
async def trigger_full_aurora_arc(
    delay_seconds: float = Query(default=0.0, ge=0.0, le=30.0),
    count: int = Query(default=3, ge=1, le=20),
    request_id: str | None = Query(default=None, min_length=1, max_length=200),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
    actor: Actor = Depends(require_actor),
) -> dict[str, Any]:
    """Start the real Aurora Durable workflow and return its tracking URLs."""
    from api.server.services.durable_client import schedule_new_orchestration

    stable_request_id = (
        idempotency_key or request_id or uuid.uuid4().hex
    ).strip()
    workflow_id, instance_id = _aurora_request_ids(stable_request_id)
    existing = app_state.store.get_workflow(workflow_id)
    payload = {
        "workflow_id": workflow_id,
        "type": "aurora-budget-response",
        "request_id": stable_request_id,
        "brand_id": "BRAND-aurora",
        "count": count,
        "requested_by": actor.id,
        "requested_by_role": actor.role,
    }
    try:
        durable = await schedule_new_orchestration(
            payload,
            function_name="AuroraBudgetResponseOrchestrator",
            instance_id=instance_id,
        )
    except Exception as exc:
        raise HTTPException(
            503,
            "Aurora Durable workflow could not be started",
        ) from exc

    workflow = app_state.store.get_workflow(workflow_id)
    if workflow is None:
        now = time.time()
        runtime_status = str(durable.get("_runtime_status") or "")
        normalised_status = runtime_status.lower().replace("_", "")
        if durable.get("_started") is False and normalised_status in {
            "completed",
        }:
            workflow_status = "completed"
        elif durable.get("_started") is False and normalised_status in {
            "failed",
            "terminated",
        }:
            workflow_status = "failed"
        else:
            workflow_status = "in_progress"
        workflow = Workflow(
            id=workflow_id,
            type="aurora-budget-response",
            status=workflow_status,
            current_phase="Observe budget signal",
            created_at=now,
            sla_due_at=now + 86400,
            jurisdiction="London-Zava",
            agency="Zava",
            orchestration_instance_id=durable.get("id") or instance_id,
            payload={
                "request_id": stable_request_id,
                "brand_id": "BRAND-aurora",
                "count": count,
            },
            metadata={
                "requested_by": actor.id,
                "delay_seconds_ignored": delay_seconds,
                **(
                    {"recovered_from_durable_status": runtime_status}
                    if durable.get("_started") is False and runtime_status
                    else {}
                ),
            },
        )
        app_state.store.upsert_workflow(workflow)
    elif not workflow.orchestration_instance_id:
        workflow.orchestration_instance_id = durable.get("id") or instance_id
        app_state.store.upsert_workflow(workflow)

    actual_instance_id = durable.get("id") or instance_id
    return {
        "workflow_id": workflow_id,
        "instance_id": actual_instance_id,
        "request_id": stable_request_id,
        "status_url": f"/api/workflows/{workflow_id}",
        "events_url": f"/api/workflows/{workflow_id}/orchestration",
        "duplicate": existing is not None or durable.get("_started") is False,
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
