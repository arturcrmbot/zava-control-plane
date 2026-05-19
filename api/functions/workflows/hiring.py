# src/functions/workflows/hiring.py
"""
The single Hiring generator orchestration — one POC2 hire end-to-end.

10 phases per [docs/archive/poc2-status.md](../../../docs/archive/poc2-status.md) §2:
  Budget -> Job Design -> Sourcing -> Triage -> Screening -> Voice ->
  Interview -> Compliance -> Offer -> Onboarding

HITL gates (mirror POC1's expense-claim pattern — `wait_for_external_event`
raced against `create_timer`, suspend/resume checkpoints either side):
  - Phase 1 (Budget) waits for the `budget_approval` external event
    (Finance BP £10k delegation per spec §4.6 multi-surface convergence)
  - Phase 9 (Offer) waits for the `offer_approval` external event
    (HR BP final approval; gates the non-revocable offer-letter send)

Reject path: an `offer_approval.decision == "reject"` short-circuits to
status=rejected, mirroring the expense-claim Arbitrate reject branch.

Skipped phases: §4.6 Voice runs only when the screening verdict is
"borderline" (flowchart in poc2-status.md). For the spine we simulate this
by checking `screening.verdict`; downstream tracks fill in the real verdict.
"""
from __future__ import annotations
import logging
import os
from collections.abc import Generator
from typing import Any

import azure.durable_functions as df

from api.shared.constants import (
    DECISION_REJECTED,
    BUDGET_APPROVAL_TIMEOUT,
    OFFER_APPROVAL_TIMEOUT,
    VOICE_SCREEN_TIMEOUT,
    INTERVIEW_INVITE_TIMEOUT,
    INTERVIEW_BOOKING_TIMEOUT,
    INTERVIEW_DECISION_TIMEOUT,
)

_log = logging.getLogger(__name__)

_VALID_SEGMENT_LETTERS = frozenset({"a", "b", "c", "d", "e", "f"})
SEGMENT_MAX_RETRIES = int(os.environ.get("SEGMENT_MAX_RETRIES", "2"))


def _parse_segments_enabled(raw: str) -> set[str]:
    """Parse HIRING_SEGMENT_MODE. Supports 'off' / '' / 'all' / comma-
    separated letters (e.g. 'b' or 'b,e'). Unknown letters dropped
    with a warning so a typo doesn't silently break the orchestrator."""
    if not raw or raw.strip().lower() == "off":
        return set()
    tokens = {t.strip().lower() for t in raw.split(",") if t.strip()}
    if "all" in tokens:
        return {"all"}
    out = tokens & _VALID_SEGMENT_LETTERS
    unknown = tokens - out
    for u in unknown:
        _log.warning("HIRING_SEGMENT_MODE: ignoring unknown letter %r", u)
    return out


def _segment_enabled(letter: str, enabled: set[str]) -> bool:
    return letter in enabled or "all" in enabled


def hiring_orchestration(context: df.DurableOrchestrationContext) -> Generator[Any, Any, dict]:
    """Orchestrate the 10 hiring phases for one req-to-hire."""
    input_dict = context.get_input() or {}
    workflow_id = input_dict.get("workflow_id", "?")
    # Stamped on every checkpoint payload so internal_durable_event populates
    # the _workflow_types cache and forwards `workflow_type` onto every
    # downstream FleetEvent. Lets the recorder/observatory resolve domain
    # for hiring runs the same way they do for travel.
    workflow_type = input_dict.get("type", "hiring")
    enriched = {**input_dict, "instance_id": context.instance_id}
    _segments_enabled = _parse_segments_enabled(os.environ.get("HIRING_SEGMENT_MODE", "off"))

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.started",
        "payload": {"poc": "poc2-hiring", "workflow_type": workflow_type},
    })

    # Phase 1: Budget — Finance BP HITL on £10k+ delegation
    budget_result = yield context.call_activity("hiring_budget_activity_trigger", enriched)
    enriched = {**enriched, "budget": budget_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        # wait_kind: external_party — Finance BP is technically internal, but
        # in the candidate-portal demo path the candidate-applied subscriber
        # auto-fires budget_approval. Treating this as a candidate-driven
        # wait keeps the operator queue clean during the demo. Engagement-POC
        # path (real Finance BP delegation) would reclassify as operator_review.
        "payload": {
            "reason": "awaiting_budget_approval", "phase": "Budget",
            "wait_kind": "external_party",
            "workflow_type": workflow_type,
            # Persona-responder contract: finance_bp applies the delegation
            # rule against the budget activity output.
            "persona": "finance_bp",
            "external_event": "budget_approval",
            "context": {
                "budget": enriched.get("budget"),
                "metadata": enriched.get("metadata"),
            },
        },
    })

    approval_event = context.wait_for_external_event("budget_approval")
    timeout_event = context.create_timer(context.current_utc_datetime + BUDGET_APPROVAL_TIMEOUT)
    winner = yield context.task_any([approval_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed", "payload": {"status": "timeout", "phase": "Budget"}
        })
        return {"status": "timeout", "phase": "Budget"}
    timeout_event.cancel()

    budget_decision = approval_event.result
    enriched["budget_approval"] = budget_decision

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed", "payload": {"phase": "Budget", "decision": budget_decision}
    })

    # Phase 2-5: Job Design / Sourcing / Triage / Screening
    if _segment_enabled("b", _segments_enabled):
        # --- Segment B: candidate discovery as one agentic loop ---
        segment_input = {**enriched, "workflow_id": context.instance_id}
        segment_result = None
        validator: dict = {}
        for attempt in range(SEGMENT_MAX_RETRIES + 1):
            segment_result = yield context.call_activity(
                "hiring_segment_b_activity_trigger", segment_input,
            )
            validator = yield context.call_activity(
                "validate_segment_b_output_activity_trigger", segment_result,
            )
            if validator.get("ok"):
                segment_result = validator["output"]
                break
            segment_input = {
                **segment_input,
                "prior_validator_error": repr(validator.get("errors")),
            }
        else:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": context.instance_id,
                "kind": "segment.failed",
                "segment": "b",
                "errors": validator.get("errors"),
            })
            raise RuntimeError(
                f"Segment B validation failed after {SEGMENT_MAX_RETRIES + 1} attempts"
            )
        # Map segment output back to the variables the rest of the
        # orchestrator expects (verdict drives Voice gating).
        screening_result = {"verdict": segment_result["verdict"], **segment_result}
        enriched = {**enriched, "screening": screening_result}
    else:
        # Phase 2: Job Design
        job_design_result = yield context.call_activity("hiring_job_design_activity_trigger", enriched)
        enriched = {**enriched, "job_design": job_design_result}

        # Phase 3: Sourcing
        sourcing_result = yield context.call_activity("hiring_sourcing_activity_trigger", enriched)
        enriched = {**enriched, "sourcing": sourcing_result}

        # Phase 4: Triage (CV crystallisation — multimodal)
        triage_result = yield context.call_activity("hiring_triage_activity_trigger", enriched)
        enriched = {**enriched, "triage": triage_result}

        # Phase 5: Screening (R/A/G-style verdict drives Voice gating)
        screening_result = yield context.call_activity("hiring_screening_activity_trigger", enriched)
        enriched = {**enriched, "screening": screening_result}

    screening_verdict = (screening_result or {}).get("verdict", "borderline")

    # Phase 6: Voice — only on borderline / strong; auto-drop short-circuits.
    if screening_verdict in {"low", "auto-drop"}:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "auto_dropped", "phase": "Screening"}
        })
        return {"status": "auto_dropped", "phase": "Screening", "screening": screening_result}

    # Phase 6: Voice screen — issue a one-shot screen-scope magic link, email
    # the candidate the /screen call URL, then suspend on `voice_complete`
    # raced against a 24h timer. The FastAPI /api/portal/voice/{id}/transcript
    # callback (raised by the firstcentral s2s accelerator's frontend on
    # call-end) fires the event with the final score.
    candidate_id = (input_dict.get("candidate_id")
                    or (enriched.get("metadata") or {}).get("candidate_id"))
    if candidate_id:
        link_result = yield context.call_activity(
            "issue_screen_link_activity_trigger",
            {"candidate_id": candidate_id},
        )
        yield context.call_activity(
            "send_screen_email_activity_trigger",
            {
                "candidate_id": candidate_id,
                "token": link_result.get("token"),
                "portal_url": link_result.get("portal_url"),
            },
        )

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "suspended",
            # wait_kind: external_party — candidate's screening call. Not an
            # operator HITL; nothing for the Agent Administrator to action.
            "payload": {
                "reason": "awaiting_voice_complete", "phase": "Voice",
                "wait_kind": "external_party",
                "workflow_type": workflow_type,
                # Persona-responder contract: candidate persona synthesises
                # a plausible voice score (~0.7–0.8) when the real candidate
                # portal isn't driving the call.
                "persona": "candidate",
                "external_event": "voice_complete",
                "context": {
                    "candidate_id": candidate_id,
                    "screen_link": link_result,
                },
            },
        })

        voice_event = context.wait_for_external_event("voice_complete")
        timeout_event = context.create_timer(
            context.current_utc_datetime + VOICE_SCREEN_TIMEOUT,
        )
        winner = yield context.task_any([voice_event, timeout_event])

        if winner == timeout_event:
            yield context.call_activity("checkpoint_activity_trigger", {
                "workflow_id": workflow_id, "instance_id": context.instance_id,
                "kind": "workflow.completed",
                "payload": {"status": "timeout", "phase": "Voice"},
            })
            return {"status": "timeout", "phase": "Voice"}
        timeout_event.cancel()

        # On callback, hand the score-bearing event payload into the voice
        # graph so the agent step still runs (gives us spans + the rubric
        # validator) but with the real transcript score in scope.
        voice_payload = voice_event.result if hasattr(voice_event, "result") else {}
        enriched_voice_input = {
            **enriched,
            "voice_event": voice_payload,
            "screen_link": link_result,
        }
        voice_result = yield context.call_activity(
            "hiring_voice_activity_trigger", enriched_voice_input,
        )
        # Surface the score the FastAPI callback raised so downstream phases
        # can read it without re-parsing the event payload.
        if isinstance(voice_payload, dict) and voice_payload.get("score") is not None:
            voice_result = {**(voice_result or {}),
                            "score": voice_payload.get("score"),
                            "duration_s": voice_payload.get("duration_s")}

        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "resumed",
            "payload": {"phase": "Voice", "score": voice_payload.get("score")
                        if isinstance(voice_payload, dict) else None},
        })
    else:
        # No candidate_id bound (legacy / spine-only test path): fall back to
        # the synchronous voice activity so existing tests keep passing.
        voice_result = yield context.call_activity(
            "hiring_voice_activity_trigger", enriched,
        )
        # Phase 7 references voice_payload unconditionally; keep it defined
        # on the legacy path so the gate-1 recommender input is well-formed.
        voice_payload = {}
    enriched = {**enriched, "voice": voice_result}

    # Phase 7: Interview — three sequential HITL waits under current_phase=Interview
    # 1) recruiter decides invite-vs-reject (gate "post_voice")
    # 2) candidate books a slot (gate "candidate_booking")
    # 3) recruiter records post-interview decision (gate "post_interview")
    # Each wait races against a timer; timeouts close the workflow as completed(timeout).

    # Pre-wait: run the recommender so the recruiter sees an AI rec.
    rec_input_gate1 = {
        **enriched,
        "gate": "post_voice",
        "cv_crystalliser": (enriched.get("triage") or {}).get("cv_crystalliser") or {},
        "screening": enriched.get("screening") or {},
        "voice_transcript": (voice_payload or {}).get("transcript") or [],
        "voice_score": (voice_payload or {}).get("score"),
    }
    yield context.call_activity(
        "hiring_interview_recommender_activity_trigger", rec_input_gate1,
    )

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_interview_invite", "phase": "Interview",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: recruiter applies the deterministic
            # green-path rule (always invite when AI rec >= shortlist).
            "persona": "recruiter",
            "external_event": "interview_invite",
            "context": {
                "gate": "post_voice",
                "triage": enriched.get("triage"),
                "screening": enriched.get("screening"),
                "voice": enriched.get("voice"),
            },
        },
    })

    invite_event = context.wait_for_external_event("interview_invite")
    timeout_event = context.create_timer(
        context.current_utc_datetime + INTERVIEW_INVITE_TIMEOUT,
    )
    winner = yield context.task_any([invite_event, timeout_event])
    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "Interview",
                        "gate": "interview_invite"},
        })
        return {"status": "timeout", "phase": "Interview"}
    timeout_event.cancel()

    invite_payload = invite_event.result if hasattr(invite_event, "result") else {}
    invite_decision = (invite_payload.get("decision") or "").lower() if isinstance(invite_payload, dict) else ""

    # Accept both the orchestrator-native vocabulary ("invite") and the
    # canonical persona verdict ("approve") that persona_responder emits.
    if invite_decision not in {"invite", "approve"}:
        # Recruiter rejected at gate 1 — auto-reject email + close workflow.
        # Pass name/email through the payload because the worker process's
        # in-memory candidate store is independent of FastAPI's.
        _cand_dict = enriched.get("candidate") or {}
        yield context.call_activity("send_rejection_email_activity_trigger", {
            "candidate_id": candidate_id,
            "gate": "interview",
            "role_title": (enriched.get("metadata") or {}).get("role_title"),
            "name": _cand_dict.get("name"),
            "email": _cand_dict.get("email"),
        })
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "by": invite_payload.get("resolved_by") if isinstance(invite_payload, dict) else None,
                "reason": invite_payload.get("reason") if isinstance(invite_payload, dict) else "recruiter rejected at interview-invite",
                "phase": "Interview",
                "gate": "interview_invite",
            },
        })
        return {"status": "rejected", "phase": "Interview", "gate": "interview_invite"}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "Interview", "gate": "interview_invite",
                    "decision": "invite"},
    })

    # Gate 2: candidate books a slot.
    book_link = yield context.call_activity(
        "issue_book_interview_link_activity_trigger",
        {"candidate_id": candidate_id},
    )
    _cand_dict = enriched.get("candidate") or {}
    yield context.call_activity(
        "send_book_interview_email_activity_trigger",
        {
            "candidate_id": candidate_id,
            "token": book_link.get("token"),
            "portal_url": book_link.get("portal_url"),
            "role_title": (enriched.get("metadata") or {}).get("role_title"),
            "name": _cand_dict.get("name"),
            "email": _cand_dict.get("email"),
        },
    )

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_interview_booking", "phase": "Interview",
            "wait_kind": "external_party",
            "workflow_type": workflow_type,
            # Persona-responder contract: candidate persona picks the first
            # available slot deterministically.
            "persona": "candidate",
            "external_event": "interview_booked",
            "context": {
                "book_link": book_link,
                "candidate": _cand_dict,
            },
        },
    })

    booked_event = context.wait_for_external_event("interview_booked")
    timeout_event = context.create_timer(
        context.current_utc_datetime + INTERVIEW_BOOKING_TIMEOUT,
    )
    winner = yield context.task_any([booked_event, timeout_event])
    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "Interview",
                        "gate": "interview_booking"},
        })
        return {"status": "timeout", "phase": "Interview"}
    timeout_event.cancel()

    booked_payload = booked_event.result if hasattr(booked_event, "result") else {}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "Interview", "gate": "interview_booking",
                    "slot": booked_payload.get("slot")
                    if isinstance(booked_payload, dict) else None},
    })

    # Gate 3: pre-decision recommender, then recruiter records.
    rec_input_gate3 = {
        **rec_input_gate1,
        "gate": "post_interview",
    }
    yield context.call_activity(
        "hiring_interview_recommender_activity_trigger", rec_input_gate3,
    )

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        "payload": {
            "reason": "awaiting_interview_complete", "phase": "Interview",
            "wait_kind": "operator_review",
            "workflow_type": workflow_type,
            # Persona-responder contract: recruiter records post-interview
            # decision (deterministic green path — always offer in v1).
            "persona": "recruiter",
            "external_event": "offer_decision",
            "context": {
                "gate": "post_interview",
                "triage": enriched.get("triage"),
                "screening": enriched.get("screening"),
                "voice": enriched.get("voice"),
                "slot": booked_payload.get("slot") if isinstance(booked_payload, dict) else None,
            },
        },
    })

    decision_event = context.wait_for_external_event("offer_decision")
    timeout_event = context.create_timer(
        context.current_utc_datetime + INTERVIEW_DECISION_TIMEOUT,
    )
    winner = yield context.task_any([decision_event, timeout_event])
    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed",
            "payload": {"status": "timeout", "phase": "Interview",
                        "gate": "interview_decision"},
        })
        return {"status": "timeout", "phase": "Interview"}
    timeout_event.cancel()

    post_payload = decision_event.result if hasattr(decision_event, "result") else {}
    post_decision = (post_payload.get("decision") or "").lower() if isinstance(post_payload, dict) else ""

    if post_decision not in {"offer", "approve"}:
        # Recruiter rejected at gate 3 — auto-reject email + close workflow.
        _cand_dict = enriched.get("candidate") or {}
        yield context.call_activity("send_rejection_email_activity_trigger", {
            "candidate_id": candidate_id,
            "gate": "offer",
            "role_title": (enriched.get("metadata") or {}).get("role_title"),
            "name": _cand_dict.get("name"),
            "email": _cand_dict.get("email"),
        })
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "by": post_payload.get("resolved_by") if isinstance(post_payload, dict) else None,
                "reason": "recruiter declined post-interview",
                "phase": "Interview",
                "gate": "interview_decision",
                "notes": post_payload.get("notes") if isinstance(post_payload, dict) else None,
                "rating": post_payload.get("rating") if isinstance(post_payload, dict) else None,
            },
        })
        return {"status": "rejected", "phase": "Interview", "gate": "interview_decision"}

    interview_result = {
        "decision": "offer",
        "level": post_payload.get("level") if isinstance(post_payload, dict) else None,
        "rating": post_payload.get("rating") if isinstance(post_payload, dict) else None,
        "notes": post_payload.get("notes") if isinstance(post_payload, dict) else None,
        "slot": booked_payload.get("slot") if isinstance(booked_payload, dict) else None,
    }
    enriched = {**enriched, "interview": interview_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed",
        "payload": {"phase": "Interview", "gate": "interview_decision",
                    "decision": "offer", "level": interview_result["level"]},
    })

    # Phase 8: Compliance (jurisdiction-aware — USA / DE BetrVG)
    compliance_result = yield context.call_activity("hiring_compliance_activity_trigger", enriched)
    enriched = {**enriched, "compliance": compliance_result}

    # Phase 9: Offer — HR BP HITL on the non-revocable offer-letter send.
    offer_result = yield context.call_activity("hiring_offer_activity_trigger", enriched)
    enriched = {**enriched, "offer": offer_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "suspended",
        # wait_kind: external_party — candidate's accept/decline. Engagement
        # POC may reclassify as operator_review when HR BP also gates the
        # non-revocable send.
        "payload": {
            "reason": "awaiting_offer_approval", "phase": "Offer",
            "wait_kind": "external_party",
            "workflow_type": workflow_type,
            # Persona-responder contract: hr_bp applies the offer-fit rule
            # against the offer activity output.
            "persona": "hr_bp",
            "external_event": "offer_approval",
            "context": {
                "offer": enriched.get("offer"),
                "compliance": enriched.get("compliance"),
                "interview": enriched.get("interview"),
            },
        },
    })

    offer_event = context.wait_for_external_event("offer_approval")
    timeout_event = context.create_timer(context.current_utc_datetime + OFFER_APPROVAL_TIMEOUT)
    winner = yield context.task_any([offer_event, timeout_event])

    if winner == timeout_event:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.completed", "payload": {"status": "timeout", "phase": "Offer"}
        })
        return {"status": "timeout", "phase": "Offer"}
    timeout_event.cancel()

    offer_decision = offer_event.result
    decision_type = (
        (offer_decision.get("decision") or "") if isinstance(offer_decision, dict) else ""
    ).lower()

    if decision_type in DECISION_REJECTED:
        yield context.call_activity("checkpoint_activity_trigger", {
            "workflow_id": workflow_id, "instance_id": context.instance_id,
            "kind": "workflow.rejected",
            "payload": {
                "by": offer_decision.get("resolved_by") if isinstance(offer_decision, dict) else None,
                "reason": "HR BP rejected offer",
                "phase": "Offer",
            },
        })
        return {"status": "rejected", "phase": "Offer", "decision": offer_decision}

    enriched["offer_approval"] = offer_decision

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "resumed", "payload": {"phase": "Offer", "decision": offer_decision}
    })

    # Phase 10: Onboarding (ServiceNow JML, HeyGen avatar, Graph invite)
    onboarding_result = yield context.call_activity("hiring_onboarding_activity_trigger", enriched)
    enriched = {**enriched, "onboarding": onboarding_result}

    yield context.call_activity("checkpoint_activity_trigger", {
        "workflow_id": workflow_id, "instance_id": context.instance_id,
        "kind": "workflow.completed", "payload": {}
    })

    return {
        "status": "completed",
        "screening_verdict": screening_verdict,
        "budget": budget_result,
        "job_design": job_design_result,
        "sourcing": sourcing_result,
        "triage": triage_result,
        "screening": screening_result,
        "voice": voice_result,
        "interview": interview_result,
        "compliance": compliance_result,
        "offer": offer_result,
        "onboarding": onboarding_result,
    }
