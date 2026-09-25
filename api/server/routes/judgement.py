"""Persona judgement: status and "ask the persona" what-ifs.

``GET /api/judgement/status`` says whether Laya is up and how many LLM deep
reviews are left this hour. ``POST /api/judgement/what-if`` asks a persona
how it would judge a waiting or decided case with one thing changed (the
agent's reasoning, or the vulnerability marker), at no token cost: it runs the
fast judgement only, changes no state, and says when a deep review would
have decided instead.
"""
from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.server.services import persona_responder
from api.server.services.judgement import engine, judgement_enabled
from api.server.services.judgement.deep_review import get_reviewer
from api.server.services.judgement.laya_client import get_client
from api.server.state import app_state

router = APIRouter(prefix="/api/judgement", tags=["judgement"])


@router.get("/status")
async def judgement_status() -> dict:
    client = get_client()
    reviewer = get_reviewer()
    return {
        "enabled": judgement_enabled(),
        "laya": {"configured": client.enabled, "available": client.available()},
        "deep_review": {"budget_per_hour": reviewer.budget.limit, "remaining": reviewer.budget.remaining(),
                        "model": reviewer.model},
    }


class WhatIf(BaseModel):
    workflow_id: str = Field(min_length=1, max_length=128)
    persona: str | None = None
    reasoning: str | None = Field(default=None, max_length=2000)
    vulnerable: bool | None = None


class _NoDeepReview:
    """A what-if never spends tokens: it reports that a deep review would decide."""

    async def review(self, request: Any) -> None:
        return None


@router.post("/what-if")
async def what_if(body: WhatIf) -> dict:
    if not judgement_enabled():
        return {"ok": False, "error": "judgement is off (JUDGEMENT_ENABLED=0)"}
    workflow = app_state.store.get_workflow(body.workflow_id)
    if workflow is None:
        return {"ok": False, "error": f"unknown workflow {body.workflow_id!r}"}
    context = copy.deepcopy((workflow.payload or {}).get("hitl_context") or {})
    if not context:
        return {"ok": False, "error": "this workflow has no decision gate to ask about"}
    role = body.persona or str(context.get("persona") or "")
    persona = persona_responder.PERSONA_DEFINITIONS.get(role)
    if persona is None or getattr(persona, "judgement", None) is None:
        return {"ok": False, "error": f"{role or 'this persona'} does not judge this gate"}

    changed: list[str] = []
    if body.reasoning is not None:
        context.setdefault("ranking", {})["reasoning"] = body.reasoning
        changed.append("the agent's reasoning")
    if body.vulnerable is not None:
        observation = context.setdefault("observation", {})
        for key in ("claim", "customer"):
            if isinstance(observation.get(key), dict):
                observation[key]["vulnerability_flag"] = body.vulnerable
        changed.append("the vulnerability marker" + (" set" if body.vulnerable else " cleared"))

    ceiling = persona.decide(context)
    ceiling = {**ceiling, "persona": ceiling.get("persona") or role}
    outcome = await engine.judge_gate(
        persona_role=role,
        persona_label=persona_responder._persona_label(role),
        instructions=getattr(persona, "skill_body", ""),
        profile=persona.judgement,
        context=context,
        ceiling=ceiling,
        workflow_id=body.workflow_id,
        gate_phase=context.get("phase"),
        next_role=persona_responder._next_role(role, context, 0, persona_responder._auto_close_set()),
        reviewer=_NoDeepReview(),
    )
    record = outcome.judgement
    if record is None:
        return {"ok": False, "error": f"{role} has no judgement profile for this gate"}
    would_deep_review = record.fallback_reason == engine.BUDGET_SPENT
    return {
        "ok": True,
        "persona": role,
        "changed": changed,
        "decision": outcome.payload.get("decision"),
        "would_deep_review": would_deep_review,
        "summary": (
            "The fast judgement is unsure here: a deep review would decide."
            if would_deep_review else record.summary()
        ),
        "judgement": record.to_dict(),
    }
