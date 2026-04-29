# src/server/services/simulator_orchestrator.py
"""
Spawns synthetic workflows by scheduling Durable Functions orchestration instances.

Week 2 pivot: ExpenseClaim is the active orchestrator; the legacy invoice
spawn_workflow is preserved for backward compatibility but no longer invoked
by the ramp loop.
"""
from __future__ import annotations
import asyncio
import json
import os
import random
from pathlib import Path

from api.server.state import app_state
from api.server.services.synthetic_data import build_workflow, build_expense_workflow
from api.server.services.durable_client import (
    schedule_new_orchestration, raise_orchestration_event,
)
from api.shared.expense_taxonomy import ReceiptFlavour

_seq = 0
_exp_seq = 0

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

# Maps a Day 7 simulator scenario to the receipt_mismatch_flavour stamped on
# the claim by the receipt PNG generator. spawn_expense_workflow picks a
# deterministic claim from the synthetic corpus matching the scenario's
# flavour so the Phase 3 receipt validator has known content to classify.
_SCENARIO_TO_FLAVOUR: dict[str, ReceiptFlavour] = {
    "receipt-mismatch-correct": "correct",
    "receipt-mismatch-amount": "wrong-amount",
    "receipt-mismatch-date": "wrong-date",
    "receipt-mismatch-vendor": "wrong-vendor",
    "receipt-missing-line": "missing-line-item",
    "receipt-missing": "missing-receipt",
}

# Module-level RNG keyed off the synthetic-data seed so picks are deterministic
# within a process and reproducible across restarts.
_scenario_rng = random.Random(20260427)


# Lazy-loaded indices over the synthetic claim corpus. The corpus is
# immutable at runtime (300 files committed to git); reading + parsing them
# on every spawn was costing ~300 file reads per ramp call.
_corpus_by_employee: dict[str, list[str]] | None = None
_corpus_by_flavour: dict[str, list[str]] | None = None


def _build_corpus_indices() -> None:
    """Walk the claim corpus once and populate both indices."""
    global _corpus_by_employee, _corpus_by_flavour
    by_employee: dict[str, list[str]] = {}
    by_flavour: dict[str, list[str]] = {}
    for path in sorted(_CLAIMS_DIR.glob("CLM-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        cid = record["claim_id"]
        emp = record.get("employee_id")
        flav = record.get("receipt_mismatch_flavour")
        if emp:
            by_employee.setdefault(emp, []).append(cid)
        if flav:
            by_flavour.setdefault(flav, []).append(cid)
    _corpus_by_employee = by_employee
    _corpus_by_flavour = by_flavour


def reset_corpus_cache() -> None:
    """Invalidate the lazy indices — call after regenerating synthetic data."""
    global _corpus_by_employee, _corpus_by_flavour
    _corpus_by_employee = None
    _corpus_by_flavour = None


def _claims_for_employee(employee_id: str) -> list[str]:
    """Return all claim_ids for a given employee, sorted by claim_id (which is
    chronological by construction). Used by the repeat-offender ramp."""
    if _corpus_by_employee is None:
        _build_corpus_indices()
    assert _corpus_by_employee is not None
    return list(_corpus_by_employee.get(employee_id, []))


def _pick_claim_for_flavour(flavour: str) -> str:
    """Pick a deterministic claim_id whose receipt_mismatch_flavour matches.
    Raises if no claim has the requested flavour."""
    if _corpus_by_flavour is None:
        _build_corpus_indices()
    assert _corpus_by_flavour is not None
    candidates = _corpus_by_flavour.get(flavour, [])
    if not candidates:
        raise ValueError(
            f"no claim with receipt_mismatch_flavour={flavour!r} in {_CLAIMS_DIR}"
        )
    return _scenario_rng.choice(candidates)


async def spawn_workflow(scenario: str | None = None) -> str:
    """Legacy: create an invoice workflow and start an InvoiceP2POrchestrator instance.

    Retained for any code/test still exercising the invoice path. The Week 2
    ramp loop spawns expense claims instead — see ``spawn_expense_workflow``.
    """
    global _seq
    _seq += 1
    wid = f"INV-{_seq:04d}"
    w = build_workflow(wid)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": w.id,
        "vendor": w.vendor.model_dump() if w.vendor else None,
        "invoice": w.invoice.model_dump() if w.invoice else None,
        "agency": w.agency,
        "jurisdiction": w.jurisdiction,
        "type": "invoice-p2p",
    }
    if scenario == "demo-fail":
        payload["force_gl_fail"] = True
    elif scenario == "demo-hitl":
        payload["force_hitl"] = True
        if payload.get("invoice"):
            payload["invoice"]["amount"] = 12500.00
    try:
        result = await schedule_new_orchestration(payload, function_name="InvoiceP2POrchestrator")
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


async def spawn_expense_workflow(
    scenario: str | None = None,
    claim_id: str | None = None,
) -> str:
    """Create an expense-claim workflow and start an ExpenseClaimOrchestrator instance.

    ``scenario`` is forwarded as a tag on the orchestration payload so downstream
    activities (Day 7+ receipt validator, Day 11 mismatch flavours) can override
    behaviour deterministically.

    ``claim_id`` deterministically picks a claim from the synthetic corpus
    (used by repeat-offender / breach-justification ramps).
    """
    global _exp_seq
    _exp_seq += 1
    wid = f"EXP-{_exp_seq:04d}"

    # Day 7 receipt-mismatch scenarios: pick a claim whose flavour matches.
    # Explicit claim_id arg wins (used by repeat-offender ramps, Day 9).
    if claim_id is None and scenario in _SCENARIO_TO_FLAVOUR:
        claim_id = _pick_claim_for_flavour(_SCENARIO_TO_FLAVOUR[scenario])

    w = build_expense_workflow(wid, claim_id=claim_id)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": w.id,
        "claim": w.claim.model_dump() if w.claim else None,
        "claim_id": w.claim.claim_id if w.claim else None,
        "ems_source": w.claim.ems_source if w.claim else None,
        "agency": w.agency,
        "jurisdiction": w.jurisdiction,
        "type": "expense-claim",
    }
    if scenario:
        payload["scenario"] = scenario
    try:
        result = await schedule_new_orchestration(
            payload, function_name="ExpenseClaimOrchestrator"
        )
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
    return wid


async def simulate_justification(
    workflow_id: str,
    text: str = "Client dinner with VP-level stakeholder; named attendees on the receipt; business reason annotated post-hoc.",
    submitted_by: str | None = None,
) -> None:
    """Day 10 round-trip: fire a `justification` external event into a Red
    workflow that's currently suspended at the Phase 5 HITL wait. The
    orchestrator resumes and proceeds to Phase 6 (Arbitrate, Week 3).

    Also emits a `justification.received` FleetEvent so the Control Plane
    surfaces the round-trip in real time.
    """
    w = app_state.store.get_workflow(workflow_id)
    if not w:
        raise KeyError(f"workflow {workflow_id!r} not found in store")
    if not w.orchestration_instance_id:
        raise ValueError(f"workflow {workflow_id!r} has no orchestration_instance_id")
    submitter = submitted_by or (
        w.claim.employee_id if getattr(w, "claim", None) else "operator"
    )
    payload = {
        "claim_id": getattr(w.claim, "claim_id", workflow_id) if getattr(w, "claim", None) else workflow_id,
        "text": text,
        "submitted_by": submitter,
        "submitted_at": _utcnow_iso(),
    }
    await raise_orchestration_event(w.orchestration_instance_id, "justification", payload)
    try:
        from api.shared.events import FleetEvent
        app_state.bus.emit(FleetEvent(
            type="justification.received",
            workflow_id=workflow_id,
            claim_id=payload["claim_id"],
            submitted_by=submitter,
        ))
    except Exception:
        pass


def _utcnow_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def spawn_repeat_offender_ramp(
    employee_id: str = "EMP-0001",
    count: int = 3,
    delay_seconds: float = 1.0,
) -> list[str]:
    """Day 9 ramp demo: spawn `count` consecutive claims from the same employee
    so the escalation_advisor's tier visibly ramps warning -> escalation ->
    major-violation across the three workflows.

    The seeded synthetic data has at least three employees (EMP-0001 et al.)
    with prior breach histories of length 2+, so the third claim should land
    in major-violation when the same-category override applies.
    """
    claim_ids = _claims_for_employee(employee_id)
    if len(claim_ids) < count:
        raise ValueError(
            f"employee {employee_id!r} has only {len(claim_ids)} claims in the corpus "
            f"(need {count}); seed more in data/synthetic/employees.json"
        )
    spawned: list[str] = []
    for cid in claim_ids[:count]:
        wid = await spawn_expense_workflow(
            scenario="repeat-offender", claim_id=cid,
        )
        spawned.append(wid)
        await asyncio.sleep(delay_seconds)
    return spawned


async def simulate_region_failure(stop_seconds: int = 10) -> dict:
    """Demo-only: emit a `region.failure.simulated` event marking the
    wall-clock window during which the operator stops the Functions host.

    Durable Functions handles checkpoint/replay natively against Azurite;
    this helper does not stop or restart anything itself — it only marks
    the audit trail and returns a snapshot of in-flight workflows so the
    UI can show before/after counts.
    """
    from api.shared.events import FleetEvent

    workflows = app_state.store.list_workflows()
    in_flight = len(workflows)
    paused = sum(1 for w in workflows if w.status == "awaiting_hitl")

    app_state.bus.emit(FleetEvent(
        type="region.failure.simulated",
        workflow_id="*",
        stop_seconds=stop_seconds,
        in_flight_count=in_flight,
        paused_at_hitl=paused,
    ))
    await asyncio.sleep(stop_seconds)
    return {
        "in_flight": in_flight,
        "paused_at_hitl": paused,
        "stop_seconds": stop_seconds,
    }


async def ramp_loop() -> None:
    """Background coroutine: spawn ExpenseClaim workflows until target, then optionally steady-state.

    Env vars:
      SIMULATOR_TARGET_WORKFLOWS — initial ramp size (0 = disabled, manual inject only).
      SIMULATOR_STEADY_STATE     — after ramp, keep spawning continuously.
                                   Default false (laptop-friendly). Set "1" to enable.
    """
    target = int(os.getenv("SIMULATOR_TARGET_WORKFLOWS", "0"))
    steady_state = os.getenv("SIMULATOR_STEADY_STATE", "0") == "1"
    if target <= 0:
        print("[orchestrator] simulator disabled (SIMULATOR_TARGET_WORKFLOWS=0); inject manually via /api/simulator/inject")
        return
    ramp_seconds = 90
    delay_per = ramp_seconds / target
    print(f"[orchestrator] ramping {target} expense-claim workflows over {ramp_seconds}s (steady_state={steady_state})")
    for _ in range(target):
        try:
            await spawn_expense_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(delay_per)
    if not steady_state:
        print("[orchestrator] ramp complete; steady-state disabled (SIMULATOR_STEADY_STATE!=1). Use /api/simulator/inject to add more.")
        return
    print("[orchestrator] ramp complete; steady-state ON")
    while True:
        try:
            await spawn_expense_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(3 + random.random() * 5)
