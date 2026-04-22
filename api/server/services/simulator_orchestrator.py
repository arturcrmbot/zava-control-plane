# src/server/services/simulator_orchestrator.py
"""
Spawns synthetic invoice workflows by scheduling InvoiceP2POrchestrator instances
on the Azure Durable Functions host. Background coroutine ramps to a target count
then steady-states.
"""
from __future__ import annotations
import asyncio
import os
import random

from api.server.state import app_state
from api.server.services.synthetic_data import build_workflow
from api.server.services.durable_client import schedule_new_orchestration

_seq = 0


async def spawn_workflow(scenario: str | None = None) -> str:
    """Create a new invoice workflow and start its DurableWorkflow instance.

    ``scenario`` selects a deterministic demo path:
      * ``"demo-fail"`` — inject ``force_gl_fail=True`` so agent_gl_coder returns
        GL-9999; validate_gl_active then blocks at Routing.
      * ``"demo-hitl"`` — inject ``force_hitl=True`` so apply_threshold_routing
        suspends regardless of amount. Amount is also bumped well above any
        reasonable threshold as belt-and-braces.
      * ``None`` / anything else — normal synthetic workflow.
    """
    global _seq
    _seq += 1
    wid = f"INV-{_seq:04d}"
    w = build_workflow(wid)
    app_state.store.upsert_workflow(w)
    payload: dict = {
        "workflow_id": w.id,
        "vendor": w.vendor.model_dump(),
        "invoice": w.invoice.model_dump(),
        "agency": w.agency,
        "jurisdiction": w.jurisdiction,
    }
    if scenario == "demo-fail":
        payload["force_gl_fail"] = True
    elif scenario == "demo-hitl":
        payload["force_hitl"] = True
        # Belt-and-braces: make the invoice amount obviously over any threshold.
        payload["invoice"]["amount"] = 12500.00
    try:
        result = await schedule_new_orchestration(payload)
        w.orchestration_instance_id = result.get("id")
        app_state.store.upsert_workflow(w)
    except Exception as ex:
        print(f"[orchestrator] failed to schedule {wid}: {ex}")
        # Workflow stays in store with no orchestration_instance_id — visible in UI as "stuck"
    return wid


async def ramp_loop() -> None:
    """Background coroutine: spawn workflows until target, then steady-state.
    SIMULATOR_TARGET_WORKFLOWS=0 disables both ramp and steady-state
    (use this on laptops; the stack can't sustain 30 concurrent MAF workflows
    because each agent step spawns GHCP SDK subprocesses that multiply fast).
    """
    target = int(os.getenv("SIMULATOR_TARGET_WORKFLOWS", "0"))
    if target <= 0:
        print("[orchestrator] simulator disabled (SIMULATOR_TARGET_WORKFLOWS=0); inject manually via /api/simulator/inject")
        return
    ramp_seconds = 90
    delay_per = ramp_seconds / target
    print(f"[orchestrator] ramping {target} workflows over {ramp_seconds}s")
    for _ in range(target):
        try:
            await spawn_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(delay_per)
    print("[orchestrator] ramp complete; steady-state")
    while True:
        try:
            await spawn_workflow()
        except Exception as ex:
            print(f"[orchestrator] spawn failed: {ex}")
        await asyncio.sleep(3 + random.random() * 5)
