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
from api.shared.vertical_loader import active_runtime

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
# Compatibility working copy for legacy tests and call sites that temporarily
# register a projection. The immutable pack mapping remains authoritative.
PROJECTIONS: dict[str, ProjectionFn] = dict(active_runtime().pack.projections)


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
