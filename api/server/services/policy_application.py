"""Persona-driven policy application.

Every persona's `summary_policy` block can emit `proposed_actions` with
`kind="policy_set"`. The cadence loop in :mod:`persona_responder` calls
:func:`apply_proposed_actions` for each new Insight so policies
self-apply without operator intervention.

The matrix at ``data/synthetic/authority/matrix.json`` is the single
gate: an action is only spawned when
``kernel().check_authority(role=persona, action="policy_set",
category=scope).allowed`` returns True. The kernel walks the matrix
deterministically; no LLM judgement is involved.

Every applied action lands as a single :class:`Decision` node via
:meth:`EntityGraph.record_decision`; every denied action is recorded as
a `policy_set.denied` audit entry with the matrix `governing_rule_id`.
The audit chain therefore preserves both outcomes — applied and denied
— with the same provenance shape as any other AGT-gated decision.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from api.server.state import app_state
from api.server.services.entity_projections import PROJECTIONS
from api.shared.events import FleetEvent
from api.shared.types import Workflow

log = logging.getLogger(__name__)


class PolicyApplicationOutcome:
    APPLIED = "applied"
    DENIED = "denied"
    UNKNOWN_KIND = "unknown_kind"
    PROJECTION_FAILED = "projection_failed"


def apply_proposed_actions(
    persona_role: str,
    proposed_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply each `kind="policy_set"` action from a persona's Insight.

    For each action:
      1. Ask the kernel whether the persona is authorised
         (``check_authority(role=persona_role, action="policy_set",
         category=action.attributes.scope)``).
      2. If allowed, spawn a one-shot ``policy_set`` workflow and record
         the resulting Decision via the projection.
      3. If denied, record an audit entry and skip.

    Returns one outcome dict per input action with keys:
      - ``id``: the action id
      - ``outcome``: one of :class:`PolicyApplicationOutcome`
      - ``workflow_id``: the spawned workflow id when applied, else None
      - ``governing_rule_id``: the matrix rule_id consulted (when known)
      - ``reason``: kernel reason when denied
    """
    from api.server.services.governance import kernel as _kernel

    outcomes: list[dict[str, Any]] = []
    for action in proposed_actions:
        if not isinstance(action, dict):
            continue
        if action.get("kind") != "policy_set":
            outcomes.append({
                "id": str(action.get("id") or ""),
                "outcome": PolicyApplicationOutcome.UNKNOWN_KIND,
                "workflow_id": None,
                "governing_rule_id": None,
                "reason": f"unsupported action kind: {action.get('kind')!r}",
            })
            continue

        attributes = dict(action.get("attributes") or {})
        scope = str(attributes.get("scope") or "")
        check = _kernel().check_authority(
            role=persona_role,
            action="policy_set",
            category=scope or None,
            requester_role=persona_role,
        )

        if not check.allowed:
            try:
                app_state.audit.log("policy_set.denied", {
                    "persona_role": persona_role,
                    "action_id": action.get("id"),
                    "scope": scope,
                    "verdict": action.get("verdict"),
                    "decided_on": list(action.get("decided_on") or []),
                    "governing_rule_id": check.governing_rule_id,
                    "reason": check.reason,
                })
            except Exception as ex:
                log.warning("policy_set.denied audit failed: %s", ex)
            outcomes.append({
                "id": str(action.get("id") or ""),
                "outcome": PolicyApplicationOutcome.DENIED,
                "workflow_id": None,
                "governing_rule_id": check.governing_rule_id,
                "reason": check.reason,
            })
            continue

        payload = {
            "persona_role": persona_role,
            "verdict": str(action.get("verdict") or ""),
            "decided_on": list(action.get("decided_on") or []),
            "attributes": attributes,
            "decisions": [{
                "phase": "policy_set",
                "verdict": str(action.get("verdict") or ""),
                "reason": str(action.get("reason") or action.get("label") or ""),
                "decided_at": "",
                "persona_role": persona_role,
            }],
        }
        workflow_id = _spawn_policy_set(
            workflow_type=str(action.get("kind") or "policy_set"),
            payload=payload,
            governing_rule_id=check.governing_rule_id,
        )
        outcomes.append({
            "id": str(action.get("id") or ""),
            "outcome": PolicyApplicationOutcome.APPLIED,
            "workflow_id": workflow_id,
            "governing_rule_id": check.governing_rule_id,
            "reason": check.reason,
        })

    return outcomes


def _spawn_policy_set(
    workflow_type: str,
    payload: dict[str, Any],
    governing_rule_id: str | None = None,
) -> str:
    """Spawn a one-shot ``policy_set`` workflow.

    Two-step shim:
      1. Emit ``workflow.spawn.requested`` on the bus so any listener
         (durable functions, audit, telemetry) sees the request.
      2. Synchronously run the matching projection and call
         ``record_decision`` so the closed loop is observable without
         external orchestration.
    """
    workflow_id = f"WF-POL-{uuid.uuid4().hex[:12]}"
    app_state.bus.emit(FleetEvent(
        type="workflow.spawn.requested",
        workflow_id=workflow_id,
        payload={
            "workflow_type": workflow_type,
            "payload": payload,
            "governing_rule_id": governing_rule_id,
        },
    ))

    project = PROJECTIONS.get(workflow_type)
    if project is None:
        return workflow_id
    now = datetime.utcnow()
    wf = Workflow(
        id=workflow_id,
        type=workflow_type,
        status="completed",
        created_at=now.timestamp(),
        sla_due_at=now.timestamp() + 3600.0,
        jurisdiction="GB",
        agency="zava",
        payload=payload,
    )
    try:
        writes = project(wf)
    except Exception as ex:
        log.warning("policy_set inline projection failed: %s", ex)
        return workflow_id
    for write in writes or []:
        if write.__class__.__name__ != "DecisionWrite":
            continue
        attrs = dict(write.attributes or {})
        if governing_rule_id:
            attrs.setdefault("governing_rule_id", governing_rule_id)
        try:
            app_state.entities.record_decision(
                workflow_id=write.workflow_id,
                phase=write.phase,
                persona_role=write.persona_role,
                verdict=write.verdict,
                reason=write.reason,
                decided_at=now,
                source_event=write.source_event,
                attributes=attrs,
                decided_on=write.decided_on,
            )
        except Exception as ex:
            log.warning("policy_set inline record_decision failed: %s", ex)
    return workflow_id
