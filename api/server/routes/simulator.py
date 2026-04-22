# src/server/routes/simulator.py
from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel
from api.server.services.simulator_orchestrator import spawn_workflow

router = APIRouter(prefix="/api/simulator")


class InjectBody(BaseModel):
    scenario: str | None = None


@router.post("/inject")
async def inject(body: InjectBody):
    workflow_id = await spawn_workflow(scenario=body.scenario)
    return {"workflow_id": workflow_id}
