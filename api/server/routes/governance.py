"""Governance routes — Phase 4 TASK-030 of plan/feature-agent-governance-toolkit-1.md.

  - GET /api/governance/verify/{workflow_id} — walk the per-workflow
    audit chain and return a :class:`VerifyReport` describing chain
    integrity (signatures + decisions resolvable land in Phase 5 + 7).

Phase 7 (TASK-053) extends this router with the kill-switch endpoints.
Operator auth follows the existing pattern on /api/authority/matrix —
the Control Plane is the only authenticated caller in the lab path.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.server.services.audit_logger import VerifyReport
from api.server.state import app_state


router = APIRouter(prefix="/api/governance")


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
