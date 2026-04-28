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
from api.server.services.durable_client import schedule_new_orchestration

_seq = 0
_exp_seq = 0

_CLAIMS_DIR = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"

# Maps a Day 7 simulator scenario to the receipt_mismatch_flavour stamped on
# the claim by the receipt PNG generator. spawn_expense_workflow picks a
# deterministic claim from the synthetic corpus matching the scenario's
# flavour so the Phase 3 receipt validator has known content to classify.
_SCENARIO_TO_FLAVOUR: dict[str, str] = {
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


def _pick_claim_for_flavour(flavour: str) -> str:
    """Pick a deterministic claim_id whose receipt_mismatch_flavour matches.

    Reads the corpus once per scenario; cheap (~300 small JSONs) and avoids
    smuggling state across invocations. Raises if no claim has the requested
    flavour."""
    candidates = []
    for path in sorted(_CLAIMS_DIR.glob("CLM-*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("receipt_mismatch_flavour") == flavour:
            candidates.append(record["claim_id"])
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


async def ramp_loop() -> None:
    """Background coroutine: spawn ExpenseClaim workflows until target, then steady-state.

    SIMULATOR_TARGET_WORKFLOWS=0 disables both ramp and steady-state.
    """
    target = int(os.getenv("SIMULATOR_TARGET_WORKFLOWS", "0"))
    if target <= 0:
        print("[orchestrator] simulator disabled (SIMULATOR_TARGET_WORKFLOWS=0); inject manually via /api/simulator/inject")
        return
    ramp_seconds = 90
    delay_per = ramp_seconds / target
    print(f"[orchestrator] ramping {target} expense-claim workflows over {ramp_seconds}s")
    for _ in range(target):
        try:
            await spawn_expense_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(delay_per)
    print("[orchestrator] ramp complete; steady-state")
    while True:
        try:
            await spawn_expense_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(3 + random.random() * 5)
