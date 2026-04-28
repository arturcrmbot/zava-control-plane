# src/server/routes/simulator.py
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field
from api.server.services.simulator_orchestrator import (
    spawn_workflow, simulate_region_failure,
)

router = APIRouter(prefix="/api/simulator")


class InjectBody(BaseModel):
    scenario: str | None = None


@router.post("/inject")
async def inject(body: InjectBody):
    workflow_id = await spawn_workflow(scenario=body.scenario)
    return {"workflow_id": workflow_id}


class RegionFailureBody(BaseModel):
    stop_seconds: int = Field(default=10, ge=1, le=120)


@router.post("/region-failure")
async def region_failure(body: RegionFailureBody):
    """Emit a `region.failure.simulated` event marking the wall-clock
    window during which the operator stops the Functions host. Used in
    the AC #11 demo to anchor the audit trail."""
    return await simulate_region_failure(stop_seconds=body.stop_seconds)
