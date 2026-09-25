"""Pack-owned workflow detail for the Banking surfaces.

Reads the shape the store actually persists (``observation``, ``decision``,
``decisions`` and ``outcome`` for the hero; ``case`` and ``decisions`` for
the supporting processes) and returns a compact, JSON-safe view rendered
under ``packDetail`` in the drawer and the spatial world panel.

It reports only what a workflow actually produced. Absent evidence yields
absent keys, never invented ones.
"""
from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _hero_detail(payload: dict[str, Any]) -> dict[str, Any]:
    observation = _dict(payload.get("observation"))
    claim = _dict(observation.get("claim"))
    customer = _dict(observation.get("customer"))
    beneficiary = _dict(observation.get("beneficiary"))
    corporate = _dict(observation.get("corporate_holder"))
    receiving_psp = _dict(observation.get("receiving_psp"))

    detail: dict[str, Any] = {}

    if claim:
        detail["claim"] = {
            "claimId": claim.get("id"),
            "amountGbp": claim.get("amount_gbp"),
            "status": claim.get("status"),
            "reimbursementCapGbp": observation.get("reimbursement_cap_gbp"),
            "vulnerabilityMarker": claim.get("vulnerability_flag"),
            "customerId": customer.get("id"),
        }

    if beneficiary:
        detail["beneficiaryPath"] = {
            "beneficiaryId": beneficiary.get("id"),
            "riskBand": beneficiary.get("risk_band"),
            "holderId": beneficiary.get("holder_id"),
            "holderKind": beneficiary.get("holder_kind"),
            "receivingPspId": receiving_psp.get("id"),
            # The seam where a retail claim and the wholesale book meet.
            "corporateHolderId": corporate.get("id") or None,
        }

    command = _dict(_dict(payload.get("decision")).get("command"))
    command_payload = _dict(command.get("payload"))
    if command_payload:
        detail["command"] = {
            "commandId": command.get("command_id"),
            "type": command.get("type"),
            "optionId": command_payload.get("option_id"),
            "valueGbp": command_payload.get("value_gbp"),
            "persona": command_payload.get("persona"),
            "decisionId": command_payload.get("decision_id"),
            "actions": [
                action.get("action_type")
                for action in _list(command_payload.get("actions"))
                if isinstance(action, dict)
            ],
        }

    outcome = _dict(payload.get("outcome"))
    if outcome:
        measurements = _dict(outcome.get("final_measurements")) or _dict(
            outcome.get("baseline")
        )
        detail["evaluation"] = {
            "status": outcome.get("status"),
            "evaluationId": outcome.get("id"),
            **({"measurements": measurements} if measurements else {}),
        }

    return detail


def _supporting_detail(payload: dict[str, Any]) -> dict[str, Any]:
    # A case the world noticed arrives as an observation that holds the case.
    case = _dict(payload.get("case")) or _dict(_dict(payload.get("observation")).get("case"))
    if not case:
        return {}
    entry = {
        "caseId": case.get("id"),
        "subjectId": case.get("subject_id"),
        "subjectKind": case.get("subject_kind"),
        "riskBand": case.get("risk_band"),
    }
    if case.get("sector"):
        entry["sector"] = case.get("sector")
    flagged = _list(case.get("flagged_payments"))
    if flagged:
        entry["flaggedPayments"] = flagged
    return {"case": entry}


def workflow_detail(workflow: Any, app_state: Any = None) -> dict[str, Any] | None:
    payload = _dict(getattr(workflow, "payload", None))
    if not payload:
        return None

    detail = _hero_detail(payload) if payload.get("observation") else {}
    if not detail:
        detail = _supporting_detail(payload)

    # A workflow stopped by the authority matrix must say so. The rejection
    # handler persists the reason and phase on the workflow's metadata, not
    # its payload, so read it from there. Without this the clearest
    # governance moment reads as an unexplained failure.
    metadata = getattr(workflow, "metadata", None)
    metadata = metadata if isinstance(metadata, dict) else {}
    if metadata.get("rejected") is True:
        detail["governanceRefusal"] = {
            "refusedAtPhase": metadata.get("rejected_at_phase"),
            "refusedBy": metadata.get("rejected_by"),
            "reason": metadata.get("rejection_reason"),
        }

    # Every governed decision this workflow recorded, with the authority rule
    # that permitted it. This is the governance story the drawer shows. A
    # judged decision also says who decided (fast judgement, deep review or
    # rules) and the concerns the persona found.
    decisions = []
    for entry in _list(payload.get("decisions")):
        if not isinstance(entry, dict):
            continue
        row = {
            "phase": entry.get("phase"),
            "persona": entry.get("persona_role"),
            "verdict": entry.get("verdict"),
            "reason": entry.get("reason"),
        }
        judgement = _dict(entry.get("judgement"))
        if entry.get("decided_by"):
            row["decidedBy"] = entry.get("decided_by")
        if judgement:
            row["concerns"] = [str(c) for c in _list(judgement.get("concerns"))]
            row["judgementSummary"] = judgement.get("summary")
            verdict = _dict(judgement.get("judge"))
            if verdict:
                row["lead"] = verdict.get("lead")
        decisions.append(row)
    if decisions:
        detail["governedDecisions"] = decisions

    return detail or None
