# src/server/routes/simulator.py
from __future__ import annotations
import time as _time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.server.services.simulator_orchestrator import (
    spawn_workflow, spawn_repeat_offender_ramp, simulate_region_failure,
)
from api.server.state import app_state
from api.shared.events import FleetEvent
from api.shared.types import ActionLedgerEntry

router = APIRouter(prefix="/api/simulator")


class InjectBody(BaseModel):
    scenario: str | None = None


@router.post("/inject")
async def inject(body: InjectBody):
    workflow_id = await spawn_workflow(scenario=body.scenario)
    return {"workflow_id": workflow_id}


class RepeatOffenderBody(BaseModel):
    employee_id: str = Field(default="EMP-0001")
    count: int = Field(default=3, ge=1, le=10)
    delay_seconds: float = Field(default=1.0, ge=0.0, le=10.0)


@router.post("/repeat-offender")
async def repeat_offender(body: RepeatOffenderBody):
    """AC #6 demo trigger: spawn `count` consecutive claims from the
    same employee so the escalation tier visibly ramps."""
    ids = await spawn_repeat_offender_ramp(
        employee_id=body.employee_id,
        count=body.count,
        delay_seconds=body.delay_seconds,
    )
    return {"workflow_ids": ids}


class RegionFailureBody(BaseModel):
    stop_seconds: int = Field(default=10, ge=1, le=120)


@router.post("/region-failure")
async def region_failure(body: RegionFailureBody):
    """Emit a `region.failure.simulated` event marking the wall-clock
    window during which the operator stops the Functions host. Used in
    the AC #11 demo to anchor the audit trail."""
    return await simulate_region_failure(stop_seconds=body.stop_seconds)


class SeedDecisionsBody(BaseModel):
    """AC #7 demo: stamp `count` synthetic reviewer.decision ledger
    entries onto an existing workflow so query_reviewer_decisions
    surfaces a cluster the FM can promote."""
    clause: str = Field(default="§3.1", description="Policy clause id")
    decision: str = Field(default="accept-justification")
    count: int = Field(default=55, ge=1, le=500)
    workflow_id: str | None = Field(
        default=None,
        description=(
            "Target workflow to attach entries to. If omitted, picks the "
            "first in-flight expense-claim workflow."
        ),
    )


@router.post("/seed-decisions")
async def seed_decisions(body: SeedDecisionsBody):
    workflow_id = body.workflow_id
    if not workflow_id:
        for w in app_state.store.list_workflows():
            if w.type == "expense-claim":
                workflow_id = w.id
                break
    if not workflow_id:
        return {"ok": False, "reason": "no expense-claim workflow available"}

    wf = app_state.store.get_workflow(workflow_id)
    if not wf:
        return {"ok": False, "reason": f"workflow {workflow_id!r} not found"}

    now = _time.time()
    for i in range(body.count):
        wf.action_ledger.append(ActionLedgerEntry(
            workflow_id=workflow_id,
            timestamp=now + i * 0.001,
            actor_kind="human",
            actor_id=f"reviewer-{(i % 7) + 1}",
            action="reviewer.decision",
            revocable=False,
            details={
                "recommendation": body.decision,
                "policy_clause": body.clause,
                "category": "meals",
            },
        ))
    return {"ok": True, "workflow_id": workflow_id, "added": body.count}


@router.post("/fleet-tick")
async def fleet_tick():
    """Manually wake the Fleet Manager. Used by the AC #7 demo beat
    after seed-decisions to force the behaviour-change loop to run."""
    app_state.bus.emit(FleetEvent(type="fleet.tick", workflow_id=None))
    return {"ok": True}
