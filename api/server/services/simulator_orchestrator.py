# src/server/services/simulator_orchestrator.py
"""
Spawns synthetic workflows by scheduling Durable Functions orchestration instances.

Week 2 pivot: ExpenseClaim is the active orchestrator; the legacy invoice
spawn_workflow is preserved for backward compatibility but no longer invoked
by the ramp loop.
"""
from __future__ import annotations
import asyncio
import os
import random

from api.server.state import app_state
from api.server.services.synthetic_data import build_workflow, build_expense_workflow
from api.server.services.durable_client import schedule_new_orchestration

_seq = 0
_exp_seq = 0


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
