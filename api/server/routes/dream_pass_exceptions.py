"""Dream-pass exception portal API.

These routes are the *only* surface where humans intervene in the
lesson lifecycle. All other paths (write, prune) are autonomous and
AGT-gated.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.server.services.audit_logger import AuditLogger
from api.server.services.entity_graph import EntityGraph
from api.server.services.governance.kernel import kernel
from api.server.services.lessons.flagged_repo import FlaggedLessonRepo
from api.server.services.lessons.governor import LessonGovernor
from api.server.services.lessons.kuzu_provenance import KuzuLessonProvenance
from api.server.services.lessons.store import InMemoryLessonStore


router = APIRouter(prefix="/api/dream-pass", tags=["dream-pass"])


def _graph() -> EntityGraph:
    # Reuse the app-wide singleton so we don't fight for the Kuzu
    # single-writer file lock. Tests patch _graph / _repo / _governor
    # directly, so this import-at-call-time pattern is fine.
    from api.server.state import app_state
    return app_state.entities


def _repo() -> FlaggedLessonRepo:
    return FlaggedLessonRepo(graph=_graph())


def _governor() -> LessonGovernor:
    return LessonGovernor(
        store=InMemoryLessonStore(),
        kernel=kernel,
        audit=AuditLogger(),
        provenance=KuzuLessonProvenance(_graph()),
        actor="operator:portal",
    )


class FlaggedItem(BaseModel):
    lesson_id: str
    body: str
    proposed_by: str
    flag_reason: str
    delta: float
    n_samples: int
    proposed_at: str | None = None
    experiment: dict[str, Any] | None = None


class FlaggedList(BaseModel):
    items: list[FlaggedItem]


class ApproveBody(BaseModel):
    approver: str = Field(..., description="operator email")


class RejectBody(BaseModel):
    reviewer: str = Field(..., description="operator email")
    reason: str = Field(..., min_length=1)


@router.get("/flagged", response_model=FlaggedList)
def list_flagged(domain: str) -> FlaggedList:
    items = _repo().list_flagged(domain=domain)
    return FlaggedList(items=[FlaggedItem(**i) for i in items])


@router.post("/flagged/{lesson_id}/approve")
def approve(lesson_id: str, body: ApproveBody) -> dict[str, str]:
    try:
        _governor().approve_flagged(lesson_id=lesson_id, approver=body.approver)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"status": "approved", "lesson_id": lesson_id}


@router.post("/flagged/{lesson_id}/reject")
def reject(lesson_id: str, body: RejectBody) -> dict[str, str]:
    _governor().reject_flagged(
        lesson_id=lesson_id, reviewer=body.reviewer, reason=body.reason
    )
    return {"status": "rejected", "lesson_id": lesson_id}
