"""Projection: expense-claim (legacy POC1).

Maps an ``expense-claim`` workflow's payload to:

* :class:`Person` ``claim_submitter`` — the employee filing the claim.
* :class:`Money` ``expense-claim`` — claim amount + currency.
* :class:`Period` ``quarter`` — accounting period derived from
  ``decided_at`` (preferred) or ``submitted_at`` on the claim.
* ``Money -[:BELONGS_TO]-> Period`` rel.
* :class:`DecisionWrite` for the ``Notify`` and ``Arbitrate`` HITL gates
  when the payload's ``decisions`` list carries matching entries (else
  skipped — see :func:`build_decision`).

Payload keys consumed (mirrors ``spawn_expense_workflow`` and the
``ClaimData`` model in :mod:`api.shared.types`)::

    claim: {
        claim_id, employee_id, submitted_at, currency, category,
        vendor, amount, ems_source, ...
    }
    decisions: [...]   # optional; per-gate dicts, see entity_projections.__init__
"""
from __future__ import annotations

from datetime import date, datetime

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "expense-claim"


def _to_date(value: str) -> date | None:
    """Coerce an ISO-8601 string to ``datetime.date`` (or ``None``)."""
    if not value:
        return None
    try:
        if "T" in value:
            return datetime.fromisoformat(value).date()
        return date.fromisoformat(value)
    except ValueError:
        return None


def _period_id_for(d: date | None, fallback_epoch: float | None) -> str:
    """Return ``PERIOD-<YYYY>-Q<n>`` for a date; fall back to the workflow
    creation epoch, then to a hard-coded sentinel."""
    if d is None and fallback_epoch:
        d = datetime.utcfromtimestamp(fallback_epoch).date()
    if d is None:
        return "PERIOD-2026-Q2"
    quarter = (d.month - 1) // 3 + 1
    return f"PERIOD-{d.year}-Q{quarter}"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    c = p.get("claim") or {}
    employee_id = str(c.get("employee_id") or p.get("employee_id") or "")
    claim_id = str(c.get("claim_id") or p.get("claim_id") or workflow.id)
    amount = c.get("amount") if "amount" in c else p.get("amount")
    amount = amount or 0
    currency = str(c.get("currency") or p.get("currency") or "GBP")
    category = str(c.get("category") or p.get("category") or "")
    vendor = str(c.get("vendor") or p.get("vendor") or "")
    submitted_at = str(c.get("submitted_at") or p.get("submitted_at") or "")

    # Period: prefer the decision timestamp on the Arbitrate gate (the
    # accounting close happens at decision time), then fall back to the
    # claim submission date, then to the workflow creation epoch.
    decisions = p.get("decisions") or []
    decided_at_raw = ""
    for entry in decisions:
        phase = str(entry.get("phase", "")).lower().replace(" ", "_")
        if phase == "arbitrate":
            decided_at_raw = str(entry.get("decided_at") or "")
            break
    period_seed = _to_date(decided_at_raw) or _to_date(submitted_at)
    period_id = _period_id_for(period_seed, workflow.created_at)

    person_id = (
        f"PERSON-{employee_id}" if employee_id
        else f"PERSON-claimant-{workflow.id}"
    )
    money_id = f"MONEY-CLAIM-{workflow.id}"
    sw = (workflow.id,)

    money_attrs: dict = {
        "kind": "expense-claim",
        "amount": float(amount),
        "currency": currency,
        "period": period_id,
    }
    if category:
        money_attrs["category"] = category
    if vendor:
        money_attrs["vendor"] = vendor

    submitted_date = _to_date(submitted_at)
    person_attrs: dict = {}
    if submitted_date is not None:
        person_attrs["claim_submitted_on"] = submitted_date

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Person",
            id=person_id,
            attrs=person_attrs,
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Money",
            id=money_id,
            attrs=money_attrs,
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Period",
            id=period_id,
            attrs={"kind": "quarter", "label": period_id.removeprefix("PERIOD-")},
        ),
        RelWrite(src_id=money_id, rel="BELONGS_TO", dst_id=period_id),
    ]

    decided_on = (person_id, money_id, period_id)
    for gate_phase, persona in (
        ("Notify", "claim_submitter"),
        ("Arbitrate", "ssc_reviewer"),
    ):
        d = build_decision(
            workflow,
            gate_phase=gate_phase,
            persona_role=persona,
            source_event="workflow.hitl.requested",
            decided_on=decided_on,
            attributes={
                "claim_id": claim_id,
                "amount": float(amount),
                "currency": currency,
            },
        )
        if d is not None:
            ops.append(d)

    return ops
