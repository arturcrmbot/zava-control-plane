"""Candidate portal routes — public /apply + token-authed /status, /offer.

See docs/superpowers/plans/2026-04-30-candidate-portal-plan.md Tasks 5-7, 13.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile, File

from api.server.state import app_state
from api.shared.events import FleetEvent

router = APIRouter(prefix="/api/portal", tags=["portal"])


# ----------------------------------------------------------------- Task 5: apply


@router.post("/apply", status_code=202)
async def apply(
    role_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    cv: UploadFile = File(...),
):
    """Public application intake.

    Validates a PDF CV upload, persists the bytes to blob storage (Azurite
    in dev; real Storage in cloud), creates a candidate record, attaches it
    to the existing HiringOrchestrator workflow keyed by `role_id`, and
    emits a `candidate.applied` event so the Triage phase can pick it up.

    Returns 415 if the upload isn't application/pdf, 404 if no workflow is
    seeded for the role, 503 if blob storage isn't configured.
    """
    if cv.content_type != "application/pdf":
        raise HTTPException(415, "cv must be application/pdf")
    if app_state.blob_store is None:
        raise HTTPException(
            503,
            "blob storage unavailable — set AZURE_STORAGE_CONNECTION_STRING",
        )
    cv_bytes = await cv.read()
    candidate_id = f"C-{uuid.uuid4().hex[:8].upper()}"
    cv_blob_name = f"cvs/{candidate_id}.pdf"
    cv_url = app_state.blob_store.put(
        cv_blob_name, cv_bytes, content_type="application/pdf",
    )
    candidate = {
        "id": candidate_id,
        "name": name,
        "email": email,
        "cv_url": cv_url,
        "role_id": role_id,
    }
    workflow_id = app_state.store.attach_candidate_to_role(role_id, candidate)
    if workflow_id is None:
        raise HTTPException(404, f"no workflow for role_id={role_id}")
    app_state.bus.emit(FleetEvent(
        type="candidate.applied",
        workflow_id=workflow_id,
        candidate_id=candidate_id,
        role_id=role_id,
    ))
    return {
        "status": "submitted",
        "candidate_id": candidate_id,
        "workflow_id": workflow_id,
    }
