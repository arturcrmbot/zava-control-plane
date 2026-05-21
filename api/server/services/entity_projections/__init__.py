"""Shared helpers for per-domain projection modules (Phase 1 sub-phase 3).

The helpers are intentionally tiny — slug normalisation and a HITL-decision
lookup convention. Per-module logic lives in the per-domain files.

Decision lookup convention
--------------------------

Workflow has no first-class ``decisions`` field today. Until one is added we
treat ``workflow.payload.get("decisions", [])`` as an opaque list of dicts
that completed orchestrators may stash on completion. Each entry is expected
to look like::

    {
        "phase": "<gate_phase>",      # matches HitlGate.gate_phase
        "verdict": "approve|reject|...",
        "reason": "...",
        "decided_at": "<iso-8601>",
        "persona_role": "<optional override>",
    }

If the payload carries no decisions (the common case in fixtures and in
mid-flight workflows), projections gracefully skip the
:class:`DecisionWrite` emission for that gate — they do *not* raise.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from api.server.services.decision_vocab import canonical_verdict
from api.server.services.entity_graph import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
)
from api.shared.types import Workflow

__all__ = [
    "DecisionWrite",
    "EntityWrite",
    "PROJECTIONS",
    "ProjectionFn",
    "RelWrite",
    "slug",
    "find_decision",
    "build_decision",
]


ProjectionFn = Callable[[Workflow], list[EntityWrite | RelWrite | DecisionWrite]]

# Registry: workflow_type → projection function. Each domain module
# registers itself by setting ``WORKFLOW_TYPE`` + ``project``; the loop at
# the bottom of this file walks every imported domain module and binds the
# registry entry.
PROJECTIONS: dict[str, ProjectionFn] = {}


_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def slug(value: str) -> str:
    """URL-safe lowercase slug: ``"Acme & Co"`` → ``"acme-co"``."""
    if not value:
        return ""
    s = _SLUG_RE.sub("-", value).strip("-").lower()
    return s or "unknown"


def find_decision(workflow: Workflow, gate_phase: str) -> dict[str, Any] | None:
    """Return the decision dict on ``workflow.payload['decisions']`` for
    ``gate_phase`` (case-insensitive, underscore/space-normalised), or
    ``None`` when the workflow has not yet completed past that gate.
    """
    decisions = workflow.payload.get("decisions") if workflow.payload else None
    if not decisions:
        return None
    target = gate_phase.lower().replace(" ", "_")
    for entry in decisions:
        phase = str(entry.get("phase", "")).lower().replace(" ", "_")
        if phase == target:
            return entry
    return None


def build_decision(
    workflow: Workflow,
    *,
    gate_phase: str,
    persona_role: str,
    source_event: str,
    decided_on: tuple[str, ...],
    attributes: dict[str, Any] | None = None,
    verdict_override: str | None = None,
) -> DecisionWrite | None:
    """Compose a :class:`DecisionWrite` for ``gate_phase`` if the payload
    carries a matching decision entry, else return ``None``.

    ``verdict_override`` (Phase 4 Task 4.1) lets a projection inject a
    wider-vocab verdict (``escalate``, ``defer``, ``request_changes``)
    based on its own policy logic, overriding whatever spelling the
    seed payload's `decisions` entry happened to ship with. The override
    is still passed through ``canonical_verdict`` so any alias in the
    override (e.g. ``"escalated"``) collapses to its canonical form.
    """
    entry = find_decision(workflow, gate_phase)
    if entry is None:
        return None
    raw_verdict = verdict_override if verdict_override is not None else entry.get("verdict", "")
    return DecisionWrite(
        workflow_id=workflow.id,
        phase=gate_phase,
        persona_role=str(entry.get("persona_role") or persona_role),
        verdict=canonical_verdict(raw_verdict),
        reason=str(entry.get("reason", "")),
        decided_at=str(entry.get("decided_at", "")),
        source_event=source_event,
        attributes=dict(attributes or {}),
        decided_on=decided_on,
    )


# Sub-phase 3: each import has the side effect of exposing
# ``WORKFLOW_TYPE`` + ``project`` on the module; the loop below binds them
# into PROJECTIONS. A missing module is therefore an explicit ImportError
# at boot rather than a silent no-op.
from . import account_onboarding    # noqa: E402  pitch-c2
from . import agency_network_roll_up  # noqa: E402  pitch-c2
from . import annual_budget_setting  # noqa: E402  pitch-c3
from . import ap_invoice            # noqa: E402  TASK-015
from . import board_prep            # noqa: E402  pitch-c1
from . import client_renewal        # noqa: E402  pitch-c3
from . import contract_renewal      # noqa: E402  TASK-021
from . import contract_review       # noqa: E402  TASK-022
from . import creative_awards_submission  # noqa: E402  pitch-c3
from . import creative_campaign     # noqa: E402  TASK-026
from . import crisis_response       # noqa: E402  pitch-c2
from . import data_clean_room_setup  # noqa: E402  pitch-c3
from . import employee_onboarding   # noqa: E402  TASK-018
from . import employee_transfer     # noqa: E402  compose-domain v4 (fleet-employee-transfer)
from . import expense_claim         # noqa: E402  pitch-a4
from . import freelancer_onboarding  # noqa: E402  pitch-c3
from . import fy_close              # noqa: E402  pitch-c1
from . import hire_to_productive    # noqa: E402  pitch-c1
from . import hiring                # noqa: E402  pitch-a4
from . import intercompany_recharge  # noqa: E402  pitch-c2
from . import intercompany_talent_transfer  # noqa: E402  pitch-c3
from . import it_access_request     # noqa: E402  TASK-019
from . import lead_to_cash          # noqa: E402  pitch-c1
from . import m_and_a_integration   # noqa: E402  pitch-c2
from . import media_pitch_to_win    # noqa: E402  pitch-c2
from . import monthly_client_pnl    # noqa: E402  pitch-c3
from . import new_business_pipeline_scrub  # noqa: E402  pitch-c3
from . import perf_review           # noqa: E402  TASK-023
from . import policy_set            # noqa: E402  autonomous-domain-insights v1
from . import privacy_dpia          # noqa: E402  TASK-024
from . import purchase_order        # noqa: E402  TASK-016
from . import quarterly_creative_awards  # noqa: E402  pitch-c3
from . import talent_redeployment   # noqa: E402  pitch-c2
from . import training_request      # noqa: E402  compose-domain v4 (fleet-training-request)
from . import travel_preapproval    # noqa: E402  TASK-020
from . import treasury_fx           # noqa: E402  TASK-025
from . import vendor_kyc            # noqa: E402  TASK-017
from . import vendor_risk_to_pay    # noqa: E402  pitch-c1
from . import weekly_pitch_review   # noqa: E402  pitch-c3

_DOMAIN_MODULES = (
    account_onboarding, agency_network_roll_up, annual_budget_setting,
    ap_invoice, board_prep, client_renewal,
    contract_renewal, contract_review, creative_awards_submission,
    creative_campaign, crisis_response, data_clean_room_setup,
    employee_onboarding, employee_transfer, expense_claim, freelancer_onboarding,
    fy_close, hire_to_productive, hiring,
    intercompany_recharge, intercompany_talent_transfer,
    it_access_request, lead_to_cash, m_and_a_integration,
    media_pitch_to_win, monthly_client_pnl, new_business_pipeline_scrub,
    perf_review, policy_set, privacy_dpia, purchase_order, quarterly_creative_awards,
    talent_redeployment, training_request, travel_preapproval, treasury_fx,
    vendor_kyc, vendor_risk_to_pay, weekly_pitch_review,
)

for _mod in _DOMAIN_MODULES:
    PROJECTIONS[_mod.WORKFLOW_TYPE] = _mod.project
