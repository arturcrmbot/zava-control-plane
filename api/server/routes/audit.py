from __future__ import annotations
from fastapi import APIRouter, Depends
from api.server.state import app_state
from api.server.services.read_route_auth import (
    Actor,
    project_for_role,
    require_actor,
)

router = APIRouter(prefix="/api/audit")


@router.get("")
@router.get("/", include_in_schema=False)
async def list_audit(actor: Actor = Depends(require_actor)):
    # Audit entries can carry persona prompts/responses inside ``details``.
    # Non-privileged actors get a redacted projection so the substrate
    # never leaks raw model content over an unauthenticated channel.
    return project_for_role(app_state.audit.list(), actor.role)
