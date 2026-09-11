from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.functions.webhook import WEBHOOK_URL, _signed_headers
from api.server.mcp_tools.invoice_repository import get_invoice


class _PolicyAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["po"]
    expiry_days: int = Field(ge=1, le=30)


class _ProposedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["freeze-brand-aurora"]
    kind: Literal["policy_set"]
    verdict: Literal["freeze"]
    decided_on: list[str] = Field(min_length=1, max_length=1)
    attributes: _PolicyAttributes
    reason: str | None = None


class AuroraRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: str = Field(min_length=1, max_length=600)
    rationale: str = Field(min_length=1, max_length=1200)
    proposed_action: _ProposedAction
    selected_invoice_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("selected_invoice_ids")
    @classmethod
    def _unique_invoice_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("selected_invoice_ids must be unique")
        return value


def _operation_url() -> str:
    parts = urlsplit(WEBHOOK_URL)
    return urlunsplit((
        parts.scheme,
        parts.netloc,
        "/internal/agency/aurora-budget-operation",
        "",
        "",
    ))


def _post_operation(body: dict) -> dict:
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    with httpx.Client() as client:
        response = client.post(
            _operation_url(),
            content=raw,
            headers=_signed_headers(raw),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()


def aurora_observe_budget_activity(payload: dict) -> dict:
    return _post_operation({
        "operation": "observe_budget",
        "workflow_id": payload["workflow_id"],
        "brand_id": payload.get("brand_id", "BRAND-aurora"),
        "target_pct": payload.get("target_pct", 1.0),
    })


def _invoice_candidates(workflow_id: str, count: int, brand_id: str) -> list[dict]:
    candidates = []
    for index in range(1, count + 1):
        invoice_id = f"INV-AUR-{workflow_id.removeprefix('AUR-')[:10]}-{index:02d}"
        record = get_invoice(invoice_id)
        candidates.append({
            **record,
            "brand_id": brand_id,
            "po_id": f"PO-AUR-{workflow_id.removeprefix('AUR-')[:10]}-{index:02d}",
            "category": record["gl_category"],
            "scenario": "matched-clean",
        })
    return candidates


async def aurora_recommendation_activity(payload: dict) -> dict:
    from api.functions.graphs.executors.agents._wrapper import run_agent_session

    workflow_id = str(payload["workflow_id"])
    count = max(1, min(20, int(payload.get("count", 3))))
    brand_id = str(payload.get("brand_id") or "BRAND-aurora")
    candidates = _invoice_candidates(workflow_id, count, brand_id)
    skill_dir = (
        Path(__file__).resolve().parents[3]
        / "verticals"
        / "agency"
        / "skills"
        / "aurora-budget-recommender"
    )
    prompt = json.dumps({
        "task": "Recommend a governed response to the observed Aurora budget signal.",
        "output_instructions": (
            "Return one JSON object matching output_schema. "
            "proposed_action is a flat object with id, kind, verdict, decided_on "
            "and attributes; do not wrap it in a policy_set property."
        ),
        "output_schema": AuroraRecommendation.model_json_schema(),
        "observation": payload["observation"],
        "invoice_candidates": candidates,
        "requested_count": count,
        "required_action": {
            "id": "freeze-brand-aurora",
            "kind": "policy_set",
            "verdict": "freeze",
            "decided_on": [brand_id],
            "attributes": {"scope": "po", "expiry_days": 14},
        },
    }, sort_keys=True)
    raw = await run_agent_session(
        prompt,
        skill_dir=skill_dir,
        skill_label="aurora-budget-recommender",
        workflow_id=workflow_id,
        instance_id=payload.get("instance_id"),
        phase="Recommend response",
    )
    recommendation = AuroraRecommendation.model_validate(raw)
    action = recommendation.proposed_action
    if (
        action.id != "freeze-brand-aurora"
        or action.kind != "policy_set"
        or action.verdict != "freeze"
        or action.decided_on != [brand_id]
        or action.attributes.scope != "po"
    ):
        raise ValueError("model recommendation violated the Aurora action boundary")
    candidate_by_id = {candidate["invoice_id"]: candidate for candidate in candidates}
    if any(
        invoice_id not in candidate_by_id
        for invoice_id in recommendation.selected_invoice_ids
    ):
        raise ValueError("model selected an invoice outside the supplied candidates")
    if len(recommendation.selected_invoice_ids) > count:
        raise ValueError("model selected more invoices than requested")
    result = recommendation.model_dump()
    result["selected_invoices"] = [
        candidate_by_id[invoice_id]
        for invoice_id in recommendation.selected_invoice_ids
    ]
    return result


def aurora_apply_policy_activity(payload: dict) -> dict:
    return _post_operation({
        "operation": "apply_policy",
        "workflow_id": payload["workflow_id"],
        "brand_id": payload.get("brand_id", "BRAND-aurora"),
        "approval": payload["approval"],
        "proposed_action": payload["proposed_action"],
    })


def aurora_synthesise_activity(payload: dict) -> dict:
    results = list(payload.get("child_results") or [])
    failed = [
        result for result in results
        if not isinstance(result, dict) or result.get("status") != "completed"
    ]
    return {
        "status": "failed" if failed else "completed",
        "queued_invoice_ids": list(payload.get("queued_invoice_ids") or []),
        "queued_count": len(payload.get("queued_invoice_ids") or []),
        "completed_count": len(results) - len(failed),
        "failed_count": len(failed),
        "child_outcomes": results,
    }
