"""Governance routes — Phase 4 TASK-030 + Phase 7 TASK-053.

  - GET    /api/governance/verify/{workflow_id}   — verify per-workflow chain.
  - GET    /api/governance/kill                   — list active kills.
  - POST   /api/governance/kill                   — add a kill.
  - DELETE /api/governance/kill/{kill_id}         — remove a kill.

Operator auth follows the existing pattern on /api/authority/matrix —
the Control Plane is the only authenticated caller in the lab path.
A real engagement-POC would slot a Bearer token check on
``api.server.routes.governance.router.dependencies`` here without
touching the route bodies.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.server.services.audit_logger import VerifyReport
from api.server.services.governance.kill_switch import (
    KillSwitch,
    kill_switch_store,
)
from api.server.state import app_state


router = APIRouter(prefix="/api/governance")


# ---------------------------------------------------------------------------
# Verify (Phase 4 TASK-030)
# ---------------------------------------------------------------------------


@router.get("/verify/{workflow_id}", response_model=VerifyReport)
async def verify_workflow(workflow_id: str) -> VerifyReport:
    """Verify the per-workflow audit hash chain.

    Returns 200 with a :class:`VerifyReport` describing chain integrity.
    A broken chain still returns 200 — the caller (Control Plane Evidence
    chip) renders the failure with ``broken_at`` + ``reason``. 404 only
    when ``workflow_id`` is empty/whitespace; an unknown id with no
    entries returns ``total_entries=0, chain_intact=true`` (vacuously).
    """
    if not workflow_id or not workflow_id.strip():
        raise HTTPException(status_code=404, detail="workflow_id is required")
    return app_state.audit.verify_chain(workflow_id.strip())


# ---------------------------------------------------------------------------
# Kill switch (Phase 7 TASK-053)
# ---------------------------------------------------------------------------


class _KillRequest(BaseModel):
    """``actor`` and ``tool`` accept ``"*"`` for wildcard. ``ttl_seconds``
    is the kill's lifetime; the kernel lazy-expires it on every call."""

    actor: str = Field(min_length=1, description="Agent id, or '*' for fleet-wide")
    tool: str = Field(min_length=1, description="Tool id, or '*' to match any")
    ttl_seconds: float = Field(
        gt=0, description="Kill lifetime in seconds (must be positive)"
    )
    reason: str = Field(min_length=1, description="Operator-visible justification")
    created_by: str = Field(default="operator")


class _KillsListResponse(BaseModel):
    kills: list[KillSwitch]
    total: int


@router.post("/kill", response_model=KillSwitch)
async def add_kill(body: _KillRequest) -> KillSwitch:
    try:
        return kill_switch_store.add(
            actor=body.actor,
            tool=body.tool,
            ttl_seconds=body.ttl_seconds,
            reason=body.reason,
            created_by=body.created_by,
        )
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))


@router.get("/kill", response_model=_KillsListResponse)
async def list_kills() -> _KillsListResponse:
    active = kill_switch_store.list_active()
    return _KillsListResponse(kills=active, total=len(active))


@router.delete("/kill/{kill_id}")
async def remove_kill(kill_id: str) -> dict[str, bool | str]:
    if not kill_id or not kill_id.strip():
        raise HTTPException(status_code=404, detail="kill_id is required")
    removed = kill_switch_store.remove(kill_id.strip())
    if not removed:
        raise HTTPException(status_code=404, detail=f"no kill with id {kill_id}")
    return {"removed": True, "kill_id": kill_id}
