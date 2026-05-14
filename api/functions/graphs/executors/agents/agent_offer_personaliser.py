"""agent_offer_personaliser — Phase 9 executor.

Generates a simple offer-letter PDF from the enriched orchestration payload,
uploads it to Azurite/Azure Blob Storage, and persists the resulting URL to
`workflow.metadata.offer_letter_url` via the FastAPI webhook bridge so the
candidate portal `/portal?token=…` can render the "View letter" button when
the workflow suspends at `awaiting_offer_approval`.

Mirrors the agent_onboarding pattern: do the heavy lifting in the Functions
worker process, then bridge the result to FastAPI's app_state.
"""
from __future__ import annotations

import io
import logging
import os

from api.functions.webhook import emit_sync as _webhook_emit_sync

log = logging.getLogger(__name__)

_BLOB_CONTAINER = os.getenv("PORTAL_OFFERS_CONTAINER", "portal-offers")


def _draw_letter(
    *,
    candidate_name: str,
    role_title: str,
    role_jurisdiction: str,
    interview_level: str | None,
    workflow_id: str,
) -> bytes:
    """Render a one-page offer letter as PDF bytes using reportlab."""
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        topMargin=0.9 * inch, bottomMargin=0.9 * inch,
        title=f"Offer Letter — {candidate_name}",
        author="Zava Talent Acquisition",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], spaceAfter=12)
    body = ParagraphStyle("body", parent=styles["BodyText"], spaceAfter=10, leading=14)
    sig = ParagraphStyle("sig", parent=styles["BodyText"], spaceBefore=24, leading=14)

    level = (interview_level or "Senior").strip()
    role = role_title or "your new role"
    juris = role_jurisdiction or "the hiring jurisdiction"

    story = [
        Paragraph("Zava — Offer of Employment", h1),
        Paragraph(f"Dear {candidate_name},", body),
        Paragraph(
            f"We are delighted to offer you the position of <b>{level} {role}</b> "
            f"based in <b>{juris}</b>. Following your interview and our internal "
            "compliance review, the hiring panel unanimously recommended you "
            "for this role.",
            body,
        ),
        Paragraph(
            "<b>Headline terms</b><br/>"
            "• Position: " + f"{level} {role}<br/>"
            "• Location: " + f"{juris}<br/>"
            "• Start date: by mutual agreement (your earliest indicated date applies)<br/>"
            "• Reporting line: as discussed with your hiring manager<br/>"
            "• Compensation, equity and benefits: per your offer summary "
            "delivered separately by our People Operations team",
            body,
        ),
        Paragraph(
            "This letter is a non-binding summary intended to confirm the role "
            "and unblock onboarding workflow steps. The full, legally binding "
            "contract of employment will follow from People Operations and "
            "supersedes this document on signature.",
            body,
        ),
        Paragraph(
            "Please review and either accept or decline using the buttons in your "
            "candidate portal. We look forward to welcoming you to the team.",
            body,
        ),
        Spacer(1, 12),
        Paragraph("Warm regards,", sig),
        Paragraph("<b>Zava Talent Acquisition</b>", body),
        Paragraph(
            f"<font size=8 color='#777777'>Reference: {workflow_id}</font>",
            body,
        ),
    ]
    doc.build(story)
    return buf.getvalue()


def _persist_offer_letter_url(workflow_id: str | None, offer_letter_url: str) -> None:
    """Bridge the URL into FastAPI's app_state via the webhook + local fallback."""
    if not workflow_id:
        return
    try:
        _webhook_emit_sync(
            workflow_id, workflow_id, "offer_letter_ready",
            {"offer_letter_url": offer_letter_url},
        )
    except Exception as exc:  # pragma: no cover — best-effort
        log.warning("webhook emit offer_letter_ready failed: %s", exc)
    try:
        from api.server.state import app_state

        wf = app_state.store.get_workflow(workflow_id)
        if wf is None:
            return
        wf.metadata = dict(wf.metadata or {})
        wf.metadata["offer_letter_url"] = offer_letter_url
        app_state.store.upsert_workflow(wf)
    except Exception as exc:  # pragma: no cover — best-effort
        log.warning("persist offer_letter_url local fallback failed: %s", exc)


def _upload_offer_letter(
    *, candidate_id: str, pdf_bytes: bytes
) -> str | None:
    """Upload to Azure Blob Storage / Azurite and return a SAS URL.

    Returns None when storage isn't configured (caller falls back to skipping
    persistence — portal renders the no-letter Offer panel).
    """
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or ""
    if not conn:
        log.warning("AZURE_STORAGE_CONNECTION_STRING unset — skipping offer letter upload")
        return None
    try:
        from api.server.services.blob_store import BlobStore

        store = BlobStore(connection_string=conn, container=_BLOB_CONTAINER)
        name = f"offers/{candidate_id}.pdf"
        store.put(name, pdf_bytes, content_type="application/pdf")
        # 7-day SAS — matches the offer magic-link TTL in the portal flow.
        return store.sas_url(name, ttl_seconds=7 * 24 * 3600)
    except Exception as exc:
        log.warning("offer letter upload failed: %s", exc)
        return None


async def execute(input: dict) -> dict:
    """Render the offer letter PDF, upload, and persist the URL onto metadata."""
    workflow_id = input.get("workflow_id") or input.get("instance_id")
    candidate_id = (
        input.get("candidate_id")
        or (input.get("candidate") or {}).get("id")
        or "UNKNOWN"
    )
    candidate_name = (
        input.get("candidate_name")
        or (input.get("candidate") or {}).get("name")
        or "there"
    )
    role_title = (
        input.get("role_title")
        or (input.get("role") or {}).get("title")
        or "your new role"
    )
    role_jurisdiction = (
        input.get("role_jurisdiction")
        or (input.get("role") or {}).get("jurisdiction")
        or ""
    )
    interview_level = (
        input.get("interview_level")
        or (input.get("interview") or {}).get("level")
    )

    out: dict = {
        "phase": "Offer",
        "workflow_id": workflow_id,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "role_title": role_title,
    }

    try:
        pdf_bytes = _draw_letter(
            candidate_name=candidate_name,
            role_title=role_title,
            role_jurisdiction=role_jurisdiction,
            interview_level=interview_level,
            workflow_id=str(workflow_id or ""),
        )
    except Exception as exc:
        log.warning("offer letter PDF render failed for workflow=%s: %s",
                    workflow_id, exc)
        out["offer_letter_error"] = str(exc)
        return out

    offer_letter_url = _upload_offer_letter(
        candidate_id=candidate_id, pdf_bytes=pdf_bytes,
    )
    if offer_letter_url:
        out["offer_letter_url"] = offer_letter_url
        _persist_offer_letter_url(workflow_id, offer_letter_url)
    else:
        out["offer_letter_skipped"] = "storage_unavailable_or_failed"

    return out
