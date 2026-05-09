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
) -> DecisionWrite | None:
    """Compose a :class:`DecisionWrite` for ``gate_phase`` if the payload
    carries a matching decision entry, else return ``None``.
    """
    entry = find_decision(workflow, gate_phase)
    if entry is None:
        return None
    return DecisionWrite(
        workflow_id=workflow.id,
        phase=gate_phase,
        persona_role=str(entry.get("persona_role") or persona_role),
        verdict=str(entry.get("verdict", "")),
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
from . import ap_invoice            # noqa: E402  TASK-015
from . import contract_renewal      # noqa: E402  TASK-021
from . import contract_review       # noqa: E402  TASK-022
from . import creative_campaign     # noqa: E402  TASK-026
from . import employee_onboarding   # noqa: E402  TASK-018
from . import it_access_request     # noqa: E402  TASK-019
from . import perf_review           # noqa: E402  TASK-023
from . import privacy_dpia          # noqa: E402  TASK-024
from . import purchase_order        # noqa: E402  TASK-016
from . import travel_preapproval    # noqa: E402  TASK-020
from . import treasury_fx           # noqa: E402  TASK-025
from . import vendor_kyc            # noqa: E402  TASK-017

_DOMAIN_MODULES = (
    ap_invoice, contract_renewal, contract_review, creative_campaign,
    employee_onboarding, it_access_request, perf_review, privacy_dpia,
    purchase_order, travel_preapproval, treasury_fx, vendor_kyc,
)

for _mod in _DOMAIN_MODULES:
    PROJECTIONS[_mod.WORKFLOW_TYPE] = _mod.project
