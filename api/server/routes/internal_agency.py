from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError

from api.server.services.governance import kernel
from api.server.services.webhook_auth import verify_hmac_signature
from api.server.state import app_state
from verticals.agency.aurora import (
    AuroraOperationConflict,
    apply_approved_policy,
    observe_budget_signal,
)


router = APIRouter(prefix="/internal/agency")


class AuroraBudgetOperation(BaseModel):
    operation: str
    workflow_id: str
    brand_id: str = "BRAND-aurora"
    target_pct: float = Field(default=1.0, gt=0.0, le=2.0)
    approval: dict = Field(default_factory=dict)
    proposed_action: dict = Field(default_factory=dict)


@router.post("/aurora-budget-operation")
async def aurora_budget_operation(
    request: Request,
    x_durable_event_signature: str | None = Header(default=None),
):
    raw = await request.body()
    verify_hmac_signature(
        secret_env="DURABLE_EVENT_SECRET",
        signature=x_durable_event_signature,
        body=raw,
    )
    try:
        body = AuroraBudgetOperation.model_validate_json(raw)
        if body.operation == "observe_budget":
            return observe_budget_signal(
                app_state.entities,
                workflow_id=body.workflow_id,
                brand_id=body.brand_id,
                target_pct=body.target_pct,
            )
        if body.operation == "apply_policy":
            return apply_approved_policy(
                app_state.entities,
                governance_kernel=kernel(),
                workflow_id=body.workflow_id,
                brand_id=body.brand_id,
                approval=body.approval,
                proposed_action=body.proposed_action,
            )
        raise HTTPException(422, f"unknown Aurora operation {body.operation!r}")
    except ValidationError as exc:
        raise HTTPException(422, detail=exc.errors()) from exc
    except AuroraOperationConflict as exc:
        raise HTTPException(409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
